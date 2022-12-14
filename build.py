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

def is_a(record_or_field, tag):
    return tag in record_or_field

def key(record_or_field):
    return next(iter(record_or_field.keys()))

def content(record_or_field):
    return next(iter(record_or_field.values()))

def field(record, tag):
    return next(filter(lambda x: is_a(x, tag), content(record)), None)

def del_field(record, tag):
    filtered = list(filter(lambda x: not is_a(x, tag), content(record)))
    content(record).clear()
    content(record).extend(filtered)

def merge(record_1, record_2):
    fields_2 = content(record_2)
    for field_2 in fields_2:
        field_1 = field(record_1, key(field_2))
        if field_1 is None:
            content(record_1).append(field_2)
        else:
            field_key = key(field_1)
            field_1.clear()
            field_1[field_key] = content(field_2)

def extract_mwse_scripts(records):
    mwse_scripts = dict()
    records_without_mwse_scripts = list()
    for record in records:
        if is_a(record, 'SCPT'):
            schd = content(field(record, 'SCHD'))
            if schd['name'].endswith('_sx'):
                name = schd['name'][:-3] + '_sc'
                schd['name'] = name
                mwse_scripts[name] = record
                continue
        records_without_mwse_scripts.append(record)
    records.clear()
    records.extend(records_without_mwse_scripts)
    return mwse_scripts

def merge_mwse_scripts(path):
    with open(path, 'r', encoding='utf-8') as f:
        records = yaml.load(f, Loader=yaml.FullLoader)
        mwse_scripts = extract_mwse_scripts(records)
        for record in records:
            if is_a(record, 'SCPT'):
                schd = content(field(record, 'SCHD'))
                mwse_script = mwse_scripts.get(schd['name'])
                if mwse_script is not None:
                    del_field(mwse_script, 'SCTX')
                    merge(record, mwse_script)
    with open(path, 'w', encoding='utf-8') as f:
        yaml.dump(records, f, allow_unicode=True)

def assembly_plugin(path, year, month, day, hour, minute, second, keep=False):
    subprocess.run(['espa', '-p', 'ru', '-v'] + (['-k'] if keep else []) + [path + '.yaml'], stdout=stdout, stderr=stderr, check=True)
    date = datetime(year=year, month=month, day=day, hour=hour, minute=minute, second=second)
    t = mktime(date.timetuple())
    utime(path, (t, t))

def reformat(path):
    subprocess.run(['espa', '-p', 'ru', '-v', path + '.yaml'], stdout=stdout, stderr=stderr, check=True)
    subprocess.run(['espa', '-p', 'ru', '-vd', path], stdout=stdout, stderr=stderr, check=True)

def write_records_count(esp_path):
    with open(esp_path, 'r', encoding='utf-8', newline='\n') as f:
        esp = yaml.load(f, Loader=yaml.FullLoader)
    esp[0]['TES3'][0]['HEDR']['records'] = len(esp) - 1
    with open(esp_path, 'w', encoding='utf-8', newline='\n') as f:
        yaml.dump(esp, f, allow_unicode=True)

def check_espa_version():
  espa = subprocess.run(['espa', '-V'], stdout=PIPE, check=True, universal_newlines=True)
  if not espa.stdout.startswith('0.11.'):
    print('wrong espa version {}'.format(espa.stdout))
    sys.exit(1)

def prepare_text(path, d):
    with open(path.upper(), 'r', encoding='utf-8', newline='\n') as utf8:
        with open(d + path + '.txt', 'w', encoding='cp1251', newline='\r\n') as cp1251:
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
    merge_mwse_scripts('ar/Data Files/A1_PrimaryNeeds_V1.esp.yaml')
    write_records_count('ar/Data Files/A1_PrimaryNeeds_V1.esp.yaml')
    assembly_plugin('ar/Data Files/A1_PrimaryNeeds_V1.esp', 2004, 2, 13, 18, 53, 0)
    make_archive('A1_PrimaryNeeds_0.4', 'ar')
    rmtree('ar')

if __name__ == "__main__":
    main()
