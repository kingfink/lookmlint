import os

import click
import yaml

from . import lookmlint


CHECK_OPTIONS = [
    'all',
    'labels',
    'sql',
    'includes',
    'view-files',
    'primary-keys',
    'duplicate-labels',
    'missing-sql-definitions',
]


def format_output(section_name, issues, ignore_yaml_default_flow_style=True):
    yaml_default_flow_style = False if ignore_yaml_default_flow_style else None
    return '\n'.join(
        [
            section_name,
            '-' * len(section_name),
            yaml.dump(issues, default_flow_style=yaml_default_flow_style),
        ]
    )


@click.group('cli')
def cli():
    pass


@click.command('lint')
@click.argument('repo-path')
@click.option(
    '--checks', required=False, type=click.STRING, default='all', show_default=True
)
def lint(repo_path, checks):
    checks = [c.strip() for c in checks.split(',')]
    for c in checks:
        if c not in CHECK_OPTIONS:
            raise click.BadOptionUsage(f'{c} not in {CHECK_OPTIONS}')
    if 'all' in checks:
        checks = list(set(CHECK_OPTIONS) - set(['all']))

    lkml = lookmlint.lookml_from_repo_path(repo_path)

    def run_check(fn, label):
        issues = fn(lkml)
        if issues == [] or issues == {}:
            return ''
        return format_output(label, issues)

    all_output = ''
    if 'labels' in checks:
        lint_config = lookmlint.read_lint_config(repo_path)
        issues = lookmlint.lint_labels(
            lkml, lint_config['acronyms'], lint_config['abbreviations']
        )
        if not (issues == [] or issues == {}):
            all_output += format_output(
                'Label Issues', issues, ignore_yaml_default_flow_style=False
            )
    if 'sql' in checks:
        all_output += run_check(
            lookmlint.lint_sql_references, 'Raw SQL Field References'
        )
    if 'includes' in checks:
        all_output += run_check(lookmlint.lint_unused_includes, 'Unused Includes')
    if 'view-files' in checks:
        all_output += run_check(lookmlint.lint_unused_view_files, 'Unused View Files')
    if 'primary-keys' in checks:
        all_output += run_check(
            lookmlint.lint_view_primary_keys, 'Views Missing Primary Keys'
        )
    if 'duplicate-labels' in checks:
        all_output += run_check(
            lookmlint.lint_duplicate_view_labels, 'Duplicate View Labels'
        )
    if 'missing-sql-definitions' in checks:
        all_output += run_check(
            lookmlint.lint_missing_view_sql_definitions, 'Missing View SQL Definitions'
        )

    if all_output != '':
        raise click.ClickException('\n' + all_output)


cli.add_command(lint)


if __name__ == '__main__':
    cli()
