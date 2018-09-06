import click

from . import lookmlint


@click.group('cli')
def cli():
    pass


@click.command('lint')
@click.argument('repo-path')
def lint(repo_path):
    lookmlint.lint(repo_path)

cli.add_command(lint)


if __name__ == '__main__':
    cli()
