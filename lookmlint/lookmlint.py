from collections import Counter
import json
import os
import subprocess

import attr
import yaml


@attr.s
class ExploreView(object):

    data = attr.ib(repr=False)
    explore = attr.ib(init=False, repr=False)
    name = attr.ib(init=False, repr=True)
    source_view = attr.ib(init=False, repr=False)

    def __attrs_post_init__(self):
        self.from_view_name = self.data.get('from')
        self.view_name = self.data.get('view_name')
        self.join_name = self.data.get('_join')
        self.explore = self.data['_explore']
        self.sql_on = self.data.get('sql_on')
        self.view_label = self.data.get('view_label')
        self.name = self._first_existing([self.view_name, self.join_name, self.explore])

    def _first_existing(self, values):
        return next(v for v in values if v is not None)

    def source_view_name(self):
        priority = [self.from_view_name, self.view_name, self.join_name, self.explore]
        return self._first_existing(priority)

    def display_label(self):
        priority = [
            self.view_label,
            self.source_view.label,
            self.name.replace('_', ' ').title(),
        ]
        return self._first_existing(priority)

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
            # doesn't contain noqa
            and not '#noqa' in line
        ]
        return len(raw_sql_words) > 0


@attr.s
class Explore(object):

    data = attr.ib(repr=False)
    label = attr.ib(init=False)
    model = attr.ib(init=False)
    name = attr.ib(init=False)
    views = attr.ib(init=False, repr=False)

    def __attrs_post_init__(self):
        self.name = self.data.get('_explore')
        self.label = self.data.get('label')
        self.model = self.data.get('_model')
        joined_views = [ExploreView(j) for j in self.data.get('joins', [])]
        self.views = [ExploreView(self.data)] + joined_views

    def display_label(self):
        return self.label if self.label else self.name.replace('_', ' ').title()

    def view_label_issues(self, acronyms=[], abbreviations=[]):
        results = {}
        for v in self.views:
            issues = label_issues(v.display_label(), acronyms, abbreviations)
            if issues == []:
                continue
            results[v.display_label()] = issues
        return results

    def duplicated_view_labels(self):
        c = Counter(v.display_label() for v in self.views)
        return {label: n for label, n in c.items() if n > 1}


@attr.s
class Model(object):

    data = attr.ib(repr=False)
    explores = attr.ib(init=False, repr=False)
    included_views = attr.ib(init=False, repr=False)
    name = attr.ib(init=False)

    def __attrs_post_init__(self):
        includes = self.data.get('include', [])
        if isinstance(includes, str):
            includes = [includes]
        self.included_views = [i[: -len('.view')] for i in includes]
        self.explores = [Explore(e) for e in self.data['explore'].values() if isinstance(e, dict)]
        self.name = self.data['_model']

    def explore_views(self):
        return [v for e in self.explores for v in e.views]

    def unused_includes(self):
        # if all views in a project are imported into a model,
        # don't suggest any includes are unused
        if self.included_views == ['*']:
            return []
        explore_view_sources = [v.source_view.name for v in self.explore_views()]
        return sorted(list(set(self.included_views) - set(explore_view_sources)))

    def explore_label_issues(self, acronyms=[], abbreviations=[]):
        results = {}
        for e in self.explores:
            issues = label_issues(e.display_label(), acronyms, abbreviations)
            if issues == []:
                continue
            results[e.display_label()] = issues
        return results


@attr.s
class View(object):

    data = attr.ib(repr=False)
    name = attr.ib(init=False)
    label = attr.ib(init=False)
    dimensions = attr.ib(init=False, repr=False)
    dimension_groups = attr.ib(init=False, repr=False)
    measures = attr.ib(init=False, repr=False)

    def __attrs_post_init__(self):
        self.name = self.data['_view']
        self.label = self.data.get('label')
        self.dimensions = [Dimension(d) for d in self.data.get('dimension', {}).values() if isinstance(d, dict)]
        self.measures = [Measure(m) for m in self.data.get('measure', {}).values() if isinstance(m, dict)]
        self.dimension_groups = [
            DimensionGroup(dg) for dg in self.data.get('dimension_group', {}).values() if isinstance(dg, dict)
        ]
        self.fields = self.dimensions + self.dimension_groups + self.measures
        self.extends = [v.strip('*') for v in self.data.get('extends', [])]
        self.sql_table_name = self.data.get('sql_table_name')
        self.derived_table_sql = None
        if 'derived_table' in self.data:
            self.derived_table_sql = self.data['derived_table']['sql']

    def field_label_issues(self, acronyms=[], abbreviations=[]):
        results = {}
        for f in self.fields:
            if f.is_hidden:
                continue
            issues = label_issues(f.display_label(), acronyms, abbreviations)
            if issues == []:
                continue
            results[f.display_label()] = issues
        return results

    def has_primary_key(self):
        return any(d.is_primary_key for d in self.dimensions)

    def has_sql_definition(self):
        return self.sql_table_name is not None or self.derived_table_sql is not None

    def derived_table_contains_semicolon(self):
        return self.derived_table_sql is not None and ';' in self.derived_table_sql


@attr.s
class Dimension(object):

    data = attr.ib(repr=False)
    name = attr.ib(init=False, repr=True)
    type = attr.ib(init=False)
    label = attr.ib(init=False)
    description = attr.ib(init=False, repr=False)

    def __attrs_post_init__(self):
        self.name = self.data['_dimension']
        self.type = self.data.get('type', 'string')
        self.label = self.data.get('label')
        self.description = self.data.get('description')
        self.sql = self.data.get('sql')
        self.is_primary_key = self.data.get('primary_key') is True
        self.is_hidden = self.data.get('hidden') is True

    def display_label(self):
        return self.label if self.label else self.name.replace('_', ' ').title()


@attr.s
class DimensionGroup(object):

    data = attr.ib(repr=False)
    name = attr.ib(init=False, repr=True)
    type = attr.ib(init=False)
    label = attr.ib(init=False)
    description = attr.ib(init=False, repr=False)
    timeframes = attr.ib(init=False, repr=False)

    def __attrs_post_init__(self):
        self.name = self.data['_dimension_group']
        self.type = self.data.get('type', 'string')
        self.label = self.data.get('label')
        self.description = self.data.get('description')
        self.sql = self.data.get('sql')
        self.timeframes = self.data.get('timeframes')
        self.is_hidden = self.data.get('hidden') is True

    def display_label(self):
        return self.label if self.label else self.name.replace('_', ' ').title()


@attr.s
class Measure(object):

    data = attr.ib(repr=False)
    name = attr.ib(init=False, repr=True)
    type = attr.ib(init=False)
    label = attr.ib(init=False)
    description = attr.ib(init=False, repr=False)

    def __attrs_post_init__(self):
        self.name = self.data['_measure']
        self.type = self.data.get('type')
        self.label = self.data.get('label')
        self.description = self.data.get('description')
        self.sql = self.data.get('sql')
        self.is_hidden = self.data.get('hidden') is True
        self.drill_fields = self.data.get('drill_fields')

    def display_label(self):
        return self.label if self.label else self.name.replace('_', ' ').title()

    def has_drill_fields(self):
        return self.drill_fields is not None or self.type in ["number", "percent_of_previous", "percent_of_total"]


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
        # match explore views with their source views
        for m in self.models:
            for e in m.explores:
                for ev in e.views:
                    source_view = next(
                        v for v in self.views if v.name == ev.source_view_name()
                    )
                    ev.source_view = source_view

    def _view_file_names(self):
        return sorted(self.data['file']['view'].keys())

    def _view(self, view_file_name):
        return list(self.data['file']['view'][view_file_name]['view'].values())[0]

    def _model_file_names(self):
        return sorted(self.data['file']['model'].keys())

    def _model(self, model_file_name):
        return self.data['file']['model'][model_file_name]['model'][model_file_name]

    def mismatched_view_names(self):
        results = {}
        for vf in self._view_file_names():
            v = View(self._view(vf))
            if v.name != vf:
                results[vf] = v.name
        return results

    def all_explore_views(self):
        explore_views = []
        for m in self.models:
            explore_views += m.explore_views()
        return explore_views

    def unused_view_files(self):
        view_names = [v.name for v in self.views]
        explore_view_names = [v.source_view.name for v in self.all_explore_views()]
        extended_views = [exv for v in self.views for exv in v.extends]
        return sorted(
            list(set(view_names) - set(explore_view_names) - set(extended_views))
        )


def read_lint_config(repo_path):
    # read .lintconfig.yml
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


def label_issues(label, acronyms=[], abbreviations=[]):
    def _contains_bad_acronym_usage(label, acronym):
        words = label.split(' ')
        # drop plural 's' from words
        if not acronym.lower().endswith('s'):
            words = [w if not w.endswith('s') else w[:-1] for w in words]
        return any(acronym.upper() == w.upper() and w == w.title() for w in words)

    def _contains_bad_abbreviation_usage(label, abbreviation):
        return any(abbreviation.lower() == k.lower() for k in label.split(' '))

    acronyms_used = [
        a.upper() for a in acronyms if _contains_bad_acronym_usage(label, a)
    ]
    abbreviations_used = [
        a.title() for a in abbreviations if _contains_bad_abbreviation_usage(label, a)
    ]
    return acronyms_used + abbreviations_used


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

    # create overall labels issues dict
    label_issues = {}
    if explore_label_issues != {}:
        label_issues['explores'] = explore_label_issues
    if explore_view_label_issues != {}:
        label_issues['explore_views'] = explore_view_label_issues
    if field_label_issues != {}:
        label_issues['fields'] = field_label_issues
    return label_issues


def lint_duplicate_view_labels(lkml):
    issues = {}
    for m in lkml.models:
        for e in m.explores:
            dupes = e.duplicated_view_labels()
            if dupes == {}:
                continue
            if m.name not in issues:
                issues[m.name] = {}
            if e.name not in issues[m.name]:
                issues[m.name][e.name] = dupes
    return issues


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


def lint_missing_drill_fields(lkml):
    # check for measures missing drill fields
    measures_missing_drill_fields = []
    for v in lkml.views:
        measures_missing_drill_fields += [(v.name, m.name) for m in v.measures if not m.has_drill_fields()]

    return sorted(list(set(measures_missing_drill_fields)))


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


def lint_missing_view_sql_definitions(lkml):
    return [
        v.name
        for v in lkml.views
        if not v.has_sql_definition()
        and v.extends == []
        and any(f.sql and '${TABLE}' in f.sql for f in v.fields)
    ]


def lint_semicolons_in_derived_table_sql(lkml):
    return [v.name for v in lkml.views if v.derived_table_contains_semicolon()]


def lint_mismatched_view_names(lkml):
    return lkml.mismatched_view_names()
