import os


import click

from . import lookmlint


CHECK_OPTIONS = ['all', 'labels', 'sql', 'includes', 'view-files', 'primary-keys']


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
    lkml = lookmlint.lookml_from_repo_path(repo_path)
    all_output = '\n'
    errors_found = False
    if 'all' in checks:
        checks = list(set(CHECK_OPTIONS) - set(['all']))
    if 'labels' in checks:
        lint_config = lookmlint.read_lint_config(repo_path)
        issues = lookmlint.lint_labels(
            lkml, lint_config['acronyms'], lint_config['abbreviations']
        )
        check_errors_found = not (issues == [] or issues == {})
        errors_found = errors_found or check_errors_found
        if check_errors_found:
            all_output += lookmlint.format_output(
                'Label Issues', issues, ignore_yaml_default_flow_style=False
            )
    if 'sql' in checks:
        issues = lookmlint.lint_sql_references(lkml)
        check_errors_found = not (issues == [] or issues == {})
        errors_found = errors_found or check_errors_found
        if check_errors_found:
            all_output += lookmlint.format_output('Raw SQL Field References', issues)
    if 'includes' in checks:
        issues = lookmlint.lint_unused_includes(lkml)
        check_errors_found = not (issues == [] or issues == {})
        errors_found = errors_found or check_errors_found
        if check_errors_found:
            all_output += lookmlint.format_output('Unused Includes', issues)
    if 'view-files' in checks:
        issues = lookmlint.lint_unused_view_files(lkml)
        check_errors_found = not (issues == [] or issues == {})
        errors_found = errors_found or check_errors_found
        if check_errors_found:
            all_output += lookmlint.format_output('Unused View Files', issues)
    if 'primary-keys' in checks:
        issues = lookmlint.lint_view_primary_keys(lkml)
        check_errors_found = not (issues == [] or issues == {})
        errors_found = errors_found or check_errors_found
        if check_errors_found:
            all_output += lookmlint.format_output('Views Missing Primary Keys', issues)

    if errors_found:
        raise click.ClickException(all_output)


cli.add_command(lint)


if __name__ == '__main__':
    cli()
