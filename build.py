from collections import namedtuple
from itertools import chain, product, combinations, count
import os, sys, shutil
from datetime import datetime
from time import mktime
from os import path, chdir, utime, remove, mkdir
from sys import stdout, stderr
import yaml
import subprocess
from subprocess import PIPE
from shutil import copyfile, move, rmtree, copytree
import re

def load_ingredients(path):
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.load(f, Loader=yaml.FullLoader)
        for record in data:
            ingr = {}
            for field in record['INGR']:
                ingr.update(field)
            if ingr.get('SCRI') is not None:
                continue
            name = ingr['NAME']
            modl = ingr['MODL']
            itex = ingr['ITEX']
            effects_data = ingr['IRDT']
            effect_1 = load_ingredient_effect(effects_data['effect_1_index'], effects_data['effect_1_attribute'], effects_data['effect_1_skill'])
            effect_2 = load_ingredient_effect(effects_data['effect_2_index'], effects_data['effect_2_attribute'], effects_data['effect_2_skill'])
            effect_3 = load_ingredient_effect(effects_data['effect_3_index'], effects_data['effect_3_attribute'], effects_data['effect_3_skill'])
            effect_4 = load_ingredient_effect(effects_data['effect_4_index'], effects_data['effect_4_attribute'], effects_data['effect_4_skill'])
            yield Ingredient(name, modl, itex, [effect_1, effect_2, effect_3, effect_4])

def gen_script(name, lines):
    return {
        'SCPT': [
            {'SCHD': {
                'name': name,
                'vars': {'shorts': 0, 'longs': 0, 'floats': 0},
                'data_size': 0,
                'var_table_size': 0
            }},
            {'SCTX': lines}
        ]
    }

def assembly_plugin(path, year, month, day, hour, minute, second, keep=False):
    subprocess.run(['espa', '-p', 'ru', '-v'] + (['-k'] if keep else []) + [path + '.yaml'], stdout=stdout, stderr=stderr, check=True)
    date = datetime(year=year, month=month, day=day, hour=hour, minute=minute, second=second)
    t = mktime(date.timetuple())
    utime(path, (t, t))

def reformat(path):
    subprocess.run(['espa', '-p', 'ru', '-v', path + '.yaml'], stdout=stdout, stderr=stderr, check=True)
    subprocess.run(['espa', '-p', 'ru', '-vd', path], stdout=stdout, stderr=stderr, check=True)

def gen_apparatus(ingrs_set, mfr, year, month, day, hour, minute, second, suffix, version):
    ingrs = { i.name: i for i in load_ingredients('ingredients/Morrowind.esm.yaml') }
    ingrs.update({ i.name: i for i in load_ingredients('ingredients/Tribunal.esm.yaml') })
    ingrs.update({ i.name: i for i in load_ingredients('ingredients/Bloodmoon.esm.yaml') })

    extra_ingrs_esp = []
    extra_ingr_files = [
        'AlterationPrecise_1C.esp.yaml',
        'Clean Ash_Grasses_20RU.esp.yaml',
        'Clean Bones11RU.esp.yaml',
        'Clean Cobwebs3.4RU.esp.yaml',
        'Clean Ferns_10_unscriptedRU.esp.yaml',
        'Clean Grasses_10RU.esp.yaml',
        'Clean Lilypads11RU.esp.yaml',
        'Clean Swamp_Scums_20_unscriptedRU.esp.yaml',
    ]
    for e in extra_ingr_files:
        ingrs.update({ i.name: i for i in load_ingredients('ingredients/' + e) })
        with open('ingredients/' + e, 'r', encoding='utf-8') as f:
            extra_ingrs_esp.extend(yaml.load(f, Loader=yaml.FullLoader))

    if ingrs_set == 'eva':
        ingrs.update({ i.name: i for i in load_ingredients('ingredients/EVA.ESP.yaml') })
    elif ingrs_set == 'mfr':
        ingrs.update({ i.name: i for i in load_ingredients('ingredients/MFR_EVA.esm.yaml') })

    ingrs = list(ingrs.values())
    ingrs.sort(key=lambda x: x.name)
    ingrs.sort(key=lambda x: len(x.name))

    add_items = []
    add_scripts = []
    check_scripts = []
    del_scripts = []
    next_useful_kind = None
    for (i, kind) in reversed(list(enumerate(kinds))):
        index = i + 1
        is_useful = False
        for level in reversed([15, 30, 45, 60]):
            level_ingrs = filter_and_group_ingredients(ingrs, kind, level)
            if not ingrs_empty(level_ingrs):
                is_useful = True
                add_items.append(gen_add_item(kind, index, level))
                add_scripts.append(gen_add_script(kind, level_ingrs, level, index))
        if is_useful:
            check_scripts.append(gen_check_script(kind, ingrs, index, next_useful_kind))
            del_scripts.append(gen_del_script(kind, ingrs, index, next_useful_kind))
        if is_useful:
            next_useful_kind = (index, kind)
    add_items.reverse()
    add_scripts.reverse()
    check_scripts.reverse()
    del_scripts.reverse()

    level_books = []
    for level in range(0, 100):
        level_books.append(gen_level_book(level))

    with open('apparatus_header.esp.yaml', 'r', encoding='utf-8') as f:
        esp_header = yaml.load(f, Loader=yaml.FullLoader)

    esp_header[0]['TES3'][0]['HEDR']['description'].append('')
    esp_header[0]['TES3'][0]['HEDR']['description'].append(version)
    esp_header[0]['TES3'][0]['HEDR']['records'] = len(esp_header) + len(add_items) + len(check_scripts) + len(add_scripts) + len(del_scripts) + len(level_books) - 1

    with open(mfr + 'alchemy_' + ingrs_set + '.esp.yaml', 'w', encoding='utf-8') as esp:
        yaml.dump(esp_header, esp, allow_unicode=True)
        yaml.dump(extra_ingrs_esp, esp, allow_unicode=True)
        yaml.dump(add_items, esp, allow_unicode=True)
        yaml.dump(add_scripts, esp, allow_unicode=True)
        yaml.dump(check_scripts, esp, allow_unicode=True)
        yaml.dump(del_scripts, esp, allow_unicode=True)
        yaml.dump(level_books, esp, allow_unicode=True)

    assembly_plugin(mfr + 'alchemy_' + ingrs_set + '.esp', year, month, day, hour, minute, second)

    with open('00_includes.au_', 'r', encoding='utf-8') as f:
        au3_includes = f.read()
    with open('01_header.au_', 'r', encoding='utf-8') as f:
        au3_header = f.read()
    with open('02_script.au_', 'r', encoding='utf-8') as f:
        au3_script = f.read()
    with open('03_close.au_', 'r', encoding='utf-8') as f:
        au3_close = f.read()
    with open('alchemy_' + ingrs_set + '.au3', 'w', encoding='utf-8') as au3:
        au3.write(au3_includes)
        au3.write('\n$ingrs_set = "' + ingrs_set +'"\n\n')
        au3.write(au3_header)
        au3.write('\n')
        au3.write('$script = "A1V7_AppaInfo_sc"\n')
        au3.write(au3_script)
        au3.write('\n')
        au3.write('$script = "A1V7_AlchemyActivator_sc"\n')
        au3.write(au3_script)
        au3.write('\n')
        au3.write('$script = "A1V7_ApparatusDeactivate_sc"\n')
        au3.write(au3_script)
        au3.write('\n')
        au3.write('$script = "A1V7_ApparatusSetUp"\n')
        au3.write(au3_script)
        au3.write('\n')
        au3.write('$script = "A1V7_Calcinator_sc"\n')
        au3.write(au3_script)
        au3.write('\n')
        au3.write('$script = "A1V7_Alembic_sc"\n')
        au3.write(au3_script)
        au3.write('\n')
        au3.write('$script = "A1V7_Retort_sc"\n')
        au3.write(au3_script)
        au3.write('\n')
        au3.write('$script = "A1V7_ApparatusItem_1_sc"\n')
        au3.write(au3_script)
        au3.write('\n')
        au3.write('$script = "A1V7_ApparatusItem_2_sc"\n')
        au3.write(au3_script)
        au3.write('\n')
        au3.write('$script = "A1V7_ApparatusItem_3_sc"\n')
        au3.write(au3_script)
        au3.write('\n')
        au3.write('$script = "A1V7_ModAlchemyExp"\n')
        au3.write(au3_script)
        au3.write('\n')
        au3.write('$script = "A1V7_CalcAlchemy2_sc"\n')
        au3.write(au3_script)
        au3.write('\n')
        au3.write('$script = "A1V7_CalcAlchemy5_sc"\n')
        au3.write(au3_script)
        au3.write('\n')
        au3.write('$script = "A1V7_StartAlchemy"\n')
        au3.write(au3_script)
        au3.write('\n')
        au3.write('$script = "A1V7_AlchemyCheck_sc"\n')
        au3.write(au3_script)
        for script in chain(check_scripts, add_scripts, del_scripts):
            script_name = script['SCPT'][0]['SCHD']['name']
            au3.write('\n')
            au3.write('$script = "' + script_name +'"\n')
            au3.write(au3_script)
        au3.write(au3_close)
    run_au3('alchemy_' + ingrs_set + '.au3')
    remove('alchemy_' + ingrs_set + '.au3')
    move(mfr + 'alchemy_' + ingrs_set + '.esp', 'A1_Alchemy_V7_Apparatus' + suffix + '.esp')
    subprocess.run('espa -p ru -vd ' + 'A1_Alchemy_V7_Apparatus' + suffix + '.esp', stdout=stdout, stderr=stderr, check=True)
    prepare_dialogs('A1_Alchemy_V7_Apparatus' + suffix)

def write_records_count(esp_path):
    with open(esp_path, 'r', encoding='utf-8') as f:
        esp = yaml.load(f, Loader=yaml.FullLoader)
    esp[0]['TES3'][0]['HEDR']['records'] = len(esp) - 1
    with open(esp_path, 'w', encoding='utf-8') as f:
        yaml.dump(esp, f, allow_unicode=True)

def check_espa_version():
  espa = subprocess.run(['espa', '-V'], stdout=PIPE, check=True, universal_newlines=True)
  if espa.stdout != '0.7.2\n':
    print('wrong espa version {}'.format(espa.stdout))
    sys.exit(1)

def prepare_text(path, d):
    with open(path.upper(), 'r', encoding='utf-8') as utf8:
        with open(d + path + '.txt', 'w', encoding='cp1251') as cp1251:
            cp1251.write(utf8.read())

def make_archive(name, dir):
    chdir(dir)
    if path.exists('../' + name + '.7z'):
        remove('../' + name + '.7z')
    subprocess.run(['7za', 'a', '../' + name + '.7z', '.'], stdout=stdout, stderr=stderr, check=True)
    chdir('..')

def represent_none(self, _):
    return self.represent_scalar('tag:yaml.org,2002:null', '~')

def main():
    cd = path.dirname(path.realpath(__file__))
    chdir(cd)
    check_espa_version()
    yaml.add_representer(type(None), represent_none)
    if path.exists('ar'):
        rmtree('ar')
    mkdir('ar')
    copytree('Data Files', 'ar/Data Files')
    #prepare_text('Readme', 'ar/')
    #prepare_text('Versions', 'ar/')
    #copytree('Screenshots', 'ar/Screenshots')
    copyfile('A1_PrimaryNeeds_V1.esp.yaml', 'ar/Data Files/A1_PrimaryNeeds_V1.esp.yaml')
    assembly_plugin('ar/Data Files/A1_PrimaryNeeds_V1.esp', 2004, 2, 13, 18, 53, 0)
    make_archive('A1_PrimaryNeeds_0.1', 'ar')
    rmtree('ar')

if __name__ == "__main__":
    main()
