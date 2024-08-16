import collections
import pathlib
import re
import sys
from itertools import zip_longest

from cldfbench import CLDFSpec, Dataset as BaseDataset


LANGUAGE_COLUMN_MAP = [
    ('ID', 'id'),
    ('Glottocode', 'id'),
    ('Family_ID', 'family_id'),
    ('Parent_ID', 'parent_id'),
    ('Name', 'name'),
    ('Latitude', 'latitude'),
    ('Longitude', 'longitude'),
    ('ISO639P3code', 'iso639P3code'),
    ('reference', 'reference'),
]

REGEX_REFERENCE = r'\\cite(?:p|t|alt)(?:\[([^\]]+)\])?\{([^}]*)\}'

# e.g.:
# * alam1246
# * yënr fëhm hɨti-bro-më-r-m
# * child pigs see-big-\textsc{r.pst-3sg.masc-3p
# *  `A child saw pig (as being) big.'
# * \citet[273]{bruce79alamblak}
EXAMPLE_COLUMNS = ['lang_id', 'text', 'gloss', 'trans', 'reference']


def patch_biblio(bibtex_code):
    bibtex_code = bibtex_code.replace(
        'Ringe, Donald A., Jr.,',
        'Ringe, Donald A. Jr.')
    bibtex_code = bibtex_code.replace(
        'Yahalom-Mack, Naama, Eliyahu-Behar, Adi',
        'Yahalom-Mack, Naama and Eliyahu-Behar, Adi')
    return bibtex_code


def add_source(row):
    reference_match = re.match(REGEX_REFERENCE, row['reference'])
    if reference_match:
        pages, bibkey = reference_match.groups()
        if pages:
            reference = '{}[{}]'.format(bibkey, pages.replace(';', ','))
        else:
            reference = bibkey
        row['Source'] = [reference]
    else:
        row['Source_comment'] = row['reference']


def make_value(row, code_table, code_id_map, param_id):
    value_row = {
        'ID': '{}-{}'.format(row['id'], param_id),
        'Language_ID': row['id'],
        'Parameter_ID': param_id,
    }
    code_id = code_id_map.get((param_id, row[param_id]))
    if code_id:
        value_row['Code_ID'] = code_id
        value_row['Value'] = code_table[code_id]['Name']
    else:
        value_row['Value'] = row[param_id]
    return value_row


def fix_example_lang_id(language_id):
    return 'wara1300' if language_id == 'wara1247' else language_id


def detex(gloss):
    gloss = gloss.replace('$\\rightarrow$', '→')
    gloss = gloss.replace('$\\emptyset$', '∅')
    gloss = gloss.replace('\\tld{}', '~')
    gloss = re.sub(
        r'\\textsc\{([^}]*)(?:\}|$)',
        lambda match: match.group(1).upper(),
        gloss)
    return gloss


def render_example(example):
    words = example['Analyzed_Word']
    glosses = example['Gloss']
    id_width = len(example['ID'])
    widths = [max(len(w), len(g)) for w, g in zip(words, glosses)]
    padded_words = [
        word.ljust(width)
        for word, width in zip_longest(words, widths, fillvalue=0)]
    padded_glosses = [
        gloss.ljust(width)
        for gloss, width in zip_longest(glosses, widths, fillvalue=0)]
    return '({})  {}\n{}    {}'.format(
        example['ID'],
        '  '.join(padded_words).rstrip(),
        ' ' * id_width,
        '  '.join(padded_glosses).rstrip())


def warn_about_glosses(example_table):
    mismatched_examples = [
        example
        for example in example_table
        if len(example['Analyzed_Word']) != len(example['Gloss'])]
    if mismatched_examples:
        print("ERROR: Misaligned glosses in examples:", file=sys.stderr)
        for example in mismatched_examples:
            print(file=sys.stderr)
            print(render_example(example), file=sys.stderr)


class Dataset(BaseDataset):
    dir = pathlib.Path(__file__).parent
    id = "jacquesestimative"

    def cldf_specs(self):  # A dataset must declare all CLDF sets it creates.
        return CLDFSpec(
            dir=self.cldf_dir,
            module='StructureDataset',
            metadata_fname='cldf-metadata.json')

    def cmd_download(self, args):
        """
        Download files to the raw/ directory. You can use helpers methods of `self.raw_dir`, e.g.

        >>> self.raw_dir.download(url, fname)
        """
        pass

    def cmd_makecldf(self, args):
        """
        Convert the raw data to a CLDF dataset.

        >>> args.writer.objects['LanguageTable'].append(...)
        """
        # read input

        raw_data = self.raw_dir.read_csv('estimative.csv', dicts=True)
        raw_examples = [
            dict(zip(EXAMPLE_COLUMNS, example))
            for example in self.raw_dir.read_csv('estimative-ex.csv')]
        bibtex_code = patch_biblio(self.raw_dir.read('bibliogj.bib'))

        parameter_table = self.etc_dir.read_csv('parameters.csv', dicts=True)
        code_table = collections.OrderedDict(
            (code['ID'], code)
            for code in self.etc_dir.read_csv('codes.csv', dicts=True))

        # cldf creation

        language_table = [
            {new_key: row[old_key]
             for new_key, old_key in LANGUAGE_COLUMN_MAP}
            for row in raw_data]
        for lang in language_table:
            add_source(lang)

        parameter_ids = [param['ID'] for param in parameter_table]
        code_id_map = {
            (code['Parameter_ID'], code['Spreadsheet_Value']): code['ID']
            for code in code_table.values()}

        value_table = [
            make_value(row, code_table, code_id_map, param_id)
            for row in raw_data
            for param_id in parameter_ids]

        example_table = [
            {
                'Language_ID': fix_example_lang_id(example['lang_id']),
                'Primary_Text': detex(example['text']),
                'Analyzed_Word': list(map(detex, example['text'].split())),
                'Gloss': list(map(detex, example['gloss'].split())),
                'Translated_Text': example['trans'].strip(),
                'reference': example['reference'],
            }
            for example in raw_examples]

        examples_per_language = collections.Counter()
        for example in example_table:
            examples_per_language[example['Language_ID']] += 1
            example['ID'] = '{}-{}'.format(
                example['Language_ID'],
                examples_per_language[example['Language_ID']])
            add_source(example)
        warn_about_glosses(example_table)

        # cldf schema

        args.writer.cldf.add_component(
            'LanguageTable',
            'Family_ID', 'Parent_ID',
            {
                'datatype': 'string',
                'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#source',
                'separator': ';',
                'name': 'Source',
            },
            'Source_comment')
        args.writer.cldf.add_component('ParameterTable')
        args.writer.cldf.add_component('CodeTable')
        args.writer.cldf.add_component(
            'ExampleTable',
            {
                'datatype': 'string',
                'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#source',
                'separator': ';',
                'name': 'Source',
            },
            'Source_comment')

        # cldf output

        args.writer.cldf.add_sources(bibtex_code)
        args.writer.objects['LanguageTable'] = language_table
        args.writer.objects['ParameterTable'] = parameter_table
        args.writer.objects['CodeTable'] = code_table.values()
        args.writer.objects['ValueTable'] = value_table
        args.writer.objects['ExampleTable'] = example_table
