import json
import os
import subprocess

import attr
import yaml


@attr.s
class LabeledResource(object):

    label = attr.ib(init=False, default=None, repr=False)

    def contains_bad_acronym_usage(self, acronym):
        return any(
            acronym.upper() == k.upper() and k != k.upper()
            for k in self.label.split(' ')
        )

    def contains_bad_abbreviation_usage(self, abbreviation):
        return any(abbreviation.lower() == k.lower() for k in self.label.split(' '))

    def label_issues(self, acronyms, abbreviations):
        acronyms_used = [
            a.upper() for a in acronyms if self.contains_bad_acronym_usage(a)
        ]
        abbreviations_used = [
            a.title() for a in abbreviations if self.contains_bad_abbreviation_usage(a)
        ]
        return acronyms_used + abbreviations_used


@attr.s
class ExploreView(LabeledResource):

    data = attr.ib(repr=False)
    explore = attr.ib(init=False, repr=False)
    label = attr.ib(init=False)
    name = attr.ib(init=False, repr=False)
    source_view = attr.ib(init=False, repr=False)

    def __attrs_post_init__(self):
        source_hierarchy = ['from', 'view_name', '_join', '_explore']
        name_hierarchy = ['view_name', '_join', '_explore']
        self.source_view = self._get_first_key(source_hierarchy)
        self.name = self._get_first_key(name_hierarchy)
        # this label needs to update based on the source view.
        # currently handling this at the LookML object level.
        self.label = self.name.replace('_', ' ').title()
        if 'view_label' in self.data:
            self.label = self.data['view_label']
        self.explore = self.data['_explore']
        self.sql_on = self.data.get('sql_on')

    def _get_first_key(self, keys):
        return next(self.data[k] for k in keys if k in self.data)

    def contains_raw_sql_ref(self):
        if not self.sql_on:
            return False
        raw_sql_words = [
            w
            for line in self.sql_on.split('\n')
            for w in line.split()
            # not a comment line
            if not line.replace(' ', '').startswith('--')
            # doesn't contain lookml syntax
            and not '${' in w and not '}' in w
            # not a custom function with newlined args
            and not w.endswith('(')
            # contains one period
            and w.count('.') == 1
        ]
        return len(raw_sql_words) > 0


@attr.s
class Explore(LabeledResource):

    data = attr.ib(repr=False)
    label = attr.ib(init=False)
    model = attr.ib(init=False)
    name = attr.ib(init=False)
    views = attr.ib(init=False, repr=False)

    def __attrs_post_init__(self):
        self.name = self.data.get('_explore')
        self.label = self.name.replace('_', ' ').title()
        if 'label' in self.data:
            self.label = self.data['label']
        self.model = self.data['_model']
        joined_views = [ExploreView(j) for j in self.data.get('joins', [])]
        self.views = [ExploreView(self.data)] + joined_views

    def view_label_issues(self, acronyms=[], abbreviations=[]):
        results = {}
        for v in self.views:
            issues = v.label_issues(acronyms, abbreviations)
            if issues == []:
                continue
            results[v.label] = issues
        return results


@attr.s
class Model(object):

    data = attr.ib(repr=False)
    explores = attr.ib(init=False, repr=False)
    included_views = attr.ib(init=False, repr=False)
    name = attr.ib(init=False)

    def __attrs_post_init__(self):
        self.included_views = [i[: -len('.view')] for i in self.data.get('include', [])]
        self.explores = [Explore(e) for e in self.data['explores']]
        self.name = self.data['_model']

    def explore_views(self):
        return [v for e in self.explores for v in e.views]

    def unused_includes(self):
        explore_view_sources = [e.source_view for e in self.explore_views()]
        return sorted(list(set(self.included_views) - set(explore_view_sources)))

    def explore_label_issues(self, acronyms=[], abbreviations=[]):
        results = {}
        for e in self.explores:
            issues = e.label_issues(acronyms, abbreviations)
            if issues == []:
                continue
            results[e.label] = issues
        return results


@attr.s
class View(LabeledResource):

    data = attr.ib(repr=False)
    name = attr.ib(init=False)
    label = attr.ib(init=False)
    dimensions = attr.ib(init=False, repr=False)
    dimension_groups = attr.ib(init=False, repr=False)
    measures = attr.ib(init=False, repr=False)

    def __attrs_post_init__(self):
        self.name = self.data['_view']
        self.label = self.name.replace('_', ' ').title()
        if 'label' in self.data:
            self.label = self.data['label']
        self.dimensions = [Dimension(d) for d in self.data.get('dimensions', [])]
        self.measures = [Measure(m) for m in self.data.get('measures', [])]
        self.dimension_groups = [
            DimensionGroup(dg) for dg in self.data.get('dimension_groups', [])
        ]
        self.fields = self.dimensions + self.dimension_groups + self.measures

    def field_label_issues(self, acronyms=[], abbreviations=[]):
        results = {}
        for f in self.fields:
            issues = f.label_issues(acronyms, abbreviations)
            if issues == []:
                continue
            results[f.label] = issues
        return results

    def has_primary_key(self):
        return any(d.is_primary_key for d in self.dimensions)


@attr.s
class Dimension(LabeledResource):

    data = attr.ib(repr=False)
    name = attr.ib(init=False, repr=False)
    type = attr.ib(init=False)
    label = attr.ib(init=False)
    description = attr.ib(init=False, repr=False)

    def __attrs_post_init__(self):
        self.name = self.data['_dimension']
        self.type = self.data.get('type', 'string')
        self.label = self.name.replace('_', ' ').title()
        if 'label' in self.data:
            self.label = self.data['label']
        self.description = self.data.get('description')
        self.is_primary_key = self.data.get('primary_key') is True


@attr.s
class DimensionGroup(LabeledResource):

    data = attr.ib(repr=False)
    name = attr.ib(init=False, repr=False)
    type = attr.ib(init=False)
    label = attr.ib(init=False)
    description = attr.ib(init=False, repr=False)
    timeframes = attr.ib(init=False, repr=False)

    def __attrs_post_init__(self):
        self.name = self.data['_dimension_group']
        self.type = self.data.get('type', 'string')
        self.label = self.name.replace('_', ' ').title()
        if 'label' in self.data:
            self.label = self.data['label']
        self.description = self.data.get('description')
        self.timeframes = self.data.get('timeframes')


@attr.s
class Measure(LabeledResource):

    data = attr.ib(repr=False)
    name = attr.ib(init=False, repr=False)
    type = attr.ib(init=False)
    label = attr.ib(init=False)
    description = attr.ib(init=False, repr=False)

    def __attrs_post_init__(self):
        self.name = self.data['_measure']
        self.type = self.data.get('type')
        self.label = self.name.replace('_', ' ').title()
        if 'label' in self.data:
            self.label = self.data['label']
        self.description = self.data.get('description')


@attr.s
class LookML(object):

    lookml_json_filepath = attr.ib()
    data = attr.ib(init=False, repr=False)
    models = attr.ib(init=False, repr=False)
    views = attr.ib(init=False, repr=False)

    def __attrs_post_init__(self):
        with open(self.lookml_json_filepath) as f:
            self.data = json.load(f)
        model_dicts = [self._model(mn) for mn in self._model_file_names()]
        self.models = [Model(m) for m in model_dicts]
        view_dicts = [self._view(vn) for vn in self._view_file_names()]
        self.views = [View(v) for v in view_dicts]
        for m in self.models:
            for e in m.explores:
                for ev in e.views:
                    source_view = next(v for v in self.views if v.name == ev.source_view)
                    if source_view.label != source_view.name.replace('_', ' ').title():
                        ev.label = source_view.label

    def _view_file_names(self):
        return sorted(self.data['file']['view'].keys())

    def _view(self, view_file_name):
        return self.data['file']['view'][view_file_name]['view'][view_file_name]

    def _model_file_names(self):
        return sorted(self.data['file']['model'].keys())

    def _model(self, model_file_name):
        return self.data['file']['model'][model_file_name]['model'][model_file_name]

    def all_explore_views(self):
        explore_views = []
        for m in self.models:
            explore_views += m.explore_views()
        return explore_views

    def unused_view_files(self):
        view_names = [v.name for v in self.views]
        explore_view_names = [ev.source_view for ev in self.all_explore_views()]
        return sorted(list(set(view_names) - set(explore_view_names)))

    def view_label_issues(self, acronyms=[], abbreviations=[]):
        results = {}
        for v in self.views:
            issues = v.label_issues(acronyms, abbreviations)
            if issues == []:
                continue
            results[v.label] = issues
        return results


def read_lint_config(repo_path):
    # read .lintconfig
    full_path = os.path.expanduser(repo_path)
    config_filepath = os.path.join(full_path, '.lintconfig.yml')
    acronyms = []
    abbreviations = []
    if os.path.isfile(config_filepath):
        with open(config_filepath) as f:
            config = yaml.load(f)
            acronyms = config.get('acronyms', acronyms)
            abbreviations = config.get('abbreviations', abbreviations)
    lint_config = {'acronyms': acronyms, 'abbreviations': abbreviations}
    return lint_config


def parse_repo(full_path):
    cmd = (
        f'cd {full_path} && '
        'lookml-parser --input="*.lkml" --whitespace=2 > /tmp/lookmlint.json'
    )
    process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    output, error = process.communicate()


def lookml_from_repo_path(repo_path):
    full_path = os.path.expanduser(repo_path)
    parse_repo(full_path)
    lkml = LookML('/tmp/lookmlint.json')
    return lkml


def lint_labels(lkml, acronyms, abbreviations):

    # check for acronym and abbreviation issues
    explore_label_issues = {}
    for m in lkml.models:
        issues = m.explore_label_issues(acronyms, abbreviations)
        if issues != {}:
            explore_label_issues[m.name] = issues
    explore_view_label_issues = {}
    for m in lkml.models:
        for e in m.explores:
            issues = e.view_label_issues(acronyms, abbreviations)
            if issues != {}:
                if m.name not in explore_view_label_issues:
                    explore_view_label_issues[m.name] = {}
                explore_view_label_issues[m.name][e.name] = issues
    field_label_issues = {}
    for v in lkml.views:
        issues = v.field_label_issues(acronyms, abbreviations)
        if issues != {}:
            field_label_issues[v.name] = issues
    view_label_issues = lkml.view_label_issues(acronyms, abbreviations)

    # create overall labels issues dict
    label_issues = {}
    if explore_label_issues != {}:
        label_issues['explores'] = explore_label_issues
    if explore_view_label_issues != {}:
        label_issues['explore_views'] = explore_view_label_issues
    if field_label_issues != {}:
        label_issues['fields'] = field_label_issues
    if view_label_issues != {}:
        label_issues['views'] = view_label_issues
    return label_issues


def lint_sql_references(lkml):
    # check for raw SQL field references
    raw_sql_refs = {}
    for m in lkml.models:
        for e in m.explores:
            for v in e.views:
                if not v.contains_raw_sql_ref():
                    continue
                if m.name not in raw_sql_refs:
                    raw_sql_refs[m.name] = {}
                if e.name not in raw_sql_refs[m.name]:
                    raw_sql_refs[m.name][e.name] = {}
                raw_sql_refs[m.name][e.name][v.name] = v.sql_on
    return raw_sql_refs


def lint_view_primary_keys(lkml):
    # check for missing primary keys
    views_missing_primary_keys = [v.name for v in lkml.views if not v.has_primary_key()]
    return views_missing_primary_keys


def lint_unused_includes(lkml):
    # check for unused includes
    unused_includes = {
        m.name: m.unused_includes() for m in lkml.models if m.unused_includes() != []
    }
    return unused_includes


def lint_unused_view_files(lkml):
    # check for unused view files
    unused_view_files = lkml.unused_view_files()
    return unused_view_files


def format_output(section_name, issues, ignore_yaml_default_flow_style=True):
    yaml_default_flow_style = False if ignore_yaml_default_flow_style else None
    return '\n'.join([
        section_name,
        '-'*50,
        yaml.dump(issues, default_flow_style=yaml_default_flow_style),
    ])


def lint(lkml, acronyms=[], abbreviations=[]):
    unused_view_files = lint_unused_view_files(lkml)
    unused_includes = lint_unused_includes(lkml)
    views_missing_primary_keys = lint_view_primary_keys(lkml)
    raw_sql_refs = lint_sql_references(lkml)
    label_issues = lint_labels(lkml, acronyms, abbreviations)

    # assemble overall issues dict
    issues = {}
    if unused_view_files != []:
        issues['unused_view_files'] = unused_view_files
    if unused_includes != {}:
        issues['unused_includes'] = unused_includes
    if views_missing_primary_keys != []:
        issues['views_missing_primary_keys'] = views_missing_primary_keys
    if label_issues != {}:
        issues['label_issues'] = label_issues
    if raw_sql_refs != {}:
        issues['raw_sql_refs'] = raw_sql_refs

    if issues == {}:
        print('No issues found!')

    # print issues
    if 'unused_view_files' in issues:
        print(format_output('Unused View Files', issues['unused_view_files']))
    if 'unused_includes' in issues:
        print(format_output('Unused Includes', issues['unused_includes']))
    if 'views_missing_primary_keys' in issues:
        print(format_output('Views Missing Primary Keys', issues['views_missing_primary_keys']))
    if 'raw_sql_refs' in issues:
        print(format_output('Raw SQL Field References', issues['raw_sql_refs']))
    if 'label_issues' in issues:
        for section, issues in issues['label_issues'].items():
            section_name = 'Label Issues - {}'.format(section.replace('_', ' ').title())
            print(format_output(section_name, issues, ignore_yaml_default_flow_style=False))
    return issues
