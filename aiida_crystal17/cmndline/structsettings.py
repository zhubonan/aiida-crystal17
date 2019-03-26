import click
from aiida.cmdline.commands.cmd_verdi import verdi
from aiida_crystal17.common import load_node, get_data_plugin
from jsonextended import edict


@verdi.group('cry17-settings')
def structsettings():
    """Commandline interface for working with StructSettingsData"""


@structsettings.command()
@click.option(
    '--symmetries', '-s', is_flag=True, help="show full symmetry operations")
@click.argument('pk', type=int)
def show(pk, symmetries):
    """show the contents of a StructSettingsData"""
    node = load_node(pk)

    if not isinstance(node, get_data_plugin('crystal17.structsettings')):
        click.echo(
            "The node was not of type 'crystal17.structsettings'", err=True)
    elif symmetries:
        edict.pprint(node.data, print_func=click.echo, round_floats=5)
    else:
        edict.pprint(node.attributes, print_func=click.echo)


@structsettings.command()
def schema():
    """view the validation schema"""
    schema = get_data_plugin('crystal17.structsettings').data_schema
    edict.pprint(schema, depth=None, print_func=click.echo)
