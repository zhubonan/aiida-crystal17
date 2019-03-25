"""a workflow to immigrate previously run CRYSTAL17 computations into Aiida"""
import os

from aiida.parsers.exceptions import ParsingError
from aiida.work import WorkChain
from aiida_crystal17.parsers.mainout_parse import parse_mainout
from aiida_crystal17.parsers.migrate import create_inputs
# from aiida.common.datastructures import calc_states
from aiida_crystal17.aiida_compatability import run_get_node


class CryMainImmigrant(WorkChain):
    """
    an immigrant calculation of CryMainCalculation
    """
    pass


# pylint: disable=too-many-locals
def migrate_as_main(input_d12_path, output_main_path,
                    jobresource_params,
                    max_wallclock_seconds=None,
                    max_memory_kb=None,
                    computer=None, computer_path=None,
                    allow_parsing_error=True,
                    encoding_in='utf8', encoding_out='utf8', in_filter=None,
                    input_links=None, test_run=False):
    """migrate existing CRYSTAL17 calculation as a WorkCalculation,
    which imitates a ``crystal17.main`` calculation

    Parameters
    ----------
    input_d12_path: str
        path to the .d12 file
    output_main_path: str
        path to the main output folder
    jobresource_params: dict
        resources of the calculation
    max_memory_kb: int or None
    max_wallclock_seconds: int or None
    computer: object or None
        the computer that the calculation was run on (if available)
    computer_path: str or None
        the path on the computer where the output files are stored
    allow_parsing_error: bool
        if True and the output file parser fails,
        the calculation will be stored with attribute status="FAILED"
    encoding_in: str
        encoding of intput file
    encoding_out: str
        encoding of output file
    in_filter: None or func
        (optional) function to parse the contents of the input file through,
        before extracting its data
    input_links=None: None or dict
        map of existing nodes to calculation inputs
        (allowed keys: 'structure', 'settings', 'parameters')
        e.g. {'structure': {"cif_file": CifNode}}

    Returns
    -------
    aiida.orm.WorkCalculation:
        the calculation node

    Raises
    ------
    IOError:
        if the work_dir or files do not exist
    aiida.common.exceptions.ParsingError:
        if the input parsing fails
    aiida.parsers.exceptions.OutputParsingError:
        if the output parsing fails

    """
    from aiida.orm.data.folder import FolderData
    from aiida.orm.data.remote import RemoteData
    from aiida_crystal17.calculations.cry_main import CryMainCalculation
    from aiida_crystal17.parsers.cry_basic import CryBasicParser

    calc = CryMainCalculation()
    parser_cls = CryBasicParser

    calc_attributes = (
        {
            "process": "CryMainImmigrant",
            "state": "FINISHED",
            "parser": parser_cls.__name__,
            "jobresource_params": dict(jobresource_params)
        }
    )
    if computer_path is not None:
        calc_attributes["remote_workdir"] = str(computer_path)
    if max_memory_kb is not None:
        calc_attributes["max_memory_kb"] = int(max_memory_kb)
    if max_wallclock_seconds is not None:
        calc_attributes["max_wallclock_seconds"] = int(max_wallclock_seconds)

    # TODO optionally use transport to remote work directory
    # to get input/output

    if not os.path.exists(input_d12_path):
        raise IOError("input_d12_path doesn't exist: "
                      "{}".format(input_d12_path))
    if not os.path.exists(output_main_path):
        raise IOError("output_main_path doesn't exist: "
                      "{}".format(output_main_path))

    inputs = create_inputs(input_d12_path, output_main_path,
                           encoding_in=encoding_in, encoding_out=encoding_out,
                           in_filter=in_filter)

    psuccess, output_nodes = parse_mainout(
        output_main_path,
        parser_class=parser_cls.__name__,
        init_struct=inputs['structure'],
        init_settings=inputs['settings'])

    outparams = output_nodes.pop("parameters")
    perrors = outparams.get_attr("errors") + outparams.get_attr(
        "parser_warnings")

    if (perrors or not psuccess):
        if not allow_parsing_error:
            raise ParsingError(
                "the parser failed, raising the following errors:\n{}".format(
                    "\n\t".join(perrors)))
        else:
            calc_attributes["state"] = 'FAILED'

    folder = FolderData()
    folder.add_path(input_d12_path, calc._DEFAULT_INPUT_FILE)
    folder.add_path(output_main_path, calc._DEFAULT_OUTPUT_FILE)

    # create links from existing nodes to inputs
    input_links = {} if not input_links else input_links
    for key, nodes_dict in input_links.items():
        _run_dummy_workchain(
            nodes_dict,
            {key: inputs[key]},
        )

    # assign linknames
    inputs_dict = {
        calc.get_linkname("parameters"): inputs['parameters'],
        calc.get_linkname("structure"): inputs['structure'],
        calc.get_linkname("settings"): inputs['settings']
    }
    for el, basis in inputs["basis"].items():
        inputs_dict[calc.get_linkname_basisset(el)] = basis

    # TODO add code input 

    outputs_dict = {parser_cls.get_linkname_outparams(): outparams}
    if "settings" in output_nodes:
        outputs_dict[parser_cls.get_linkname_outsettings()] = output_nodes.pop(
            "settings")
    if "structure" in output_nodes:
        outputs_dict[parser_cls.get_linkname_outstructure(
        )] = output_nodes.pop("structure")
    if output_nodes:
        raise ParsingError("unknown key(s) in output_nodes: {}".format(
            list(output_nodes.keys())))

    outputs_dict["retrieved"] = folder

    if computer is not None and computer_path is not None:
        remote = RemoteData()
        remote.set_computer(computer)
        remote.set_remote_path(computer_path)
        outputs_dict["remote_folder"] = remote

    calcnode = _run_dummy_workchain(inputs_dict, outputs_dict,
                                    CryMainImmigrant)

    calcnode.label = "CryMainImmigrant"
    calcnode.description = (
        "an immigrated CRYSTAL17 calculation into the {} format").format(
        calc.__class__)

    # TODO this is hack and will only work for aiida < v1
    calcnode._updatable_attributes = tuple(
        list(calcnode._updatable_attributes) + list(calc_attributes.keys()))
    calcnode.SEALED_KEY = False
    for key, val in calc_attributes.items():
        calcnode._set_attr(key, val)
    calcnode.SEALED_KEY = True

    return calcnode


def _run_dummy_workchain(inputs_dict, outputs_dict, workchain_cls=None):
    """ create a bespoke workchain with the required inputs and outputs

    :param inputs_dict: dict mapping input node names to the nodes
    :param outputs_dict: dict mapping output node names to the nodes
    :param workchain_cls: the workchain class from which to inherit
    :return: the calculation node
    """
    workchain_cls = WorkChain if workchain_cls is None else workchain_cls

    class DummyProcess(workchain_cls):
        @classmethod
        def define(cls, spec):
            super(DummyProcess, cls).define(spec)
            for name in inputs_dict:
                spec.input(name)
            spec.outline(cls.compute, )
            for oname in outputs_dict:
                spec.output(oname)

        def compute(self):
            for name, data in outputs_dict.items():
                self.out(name, data)

    calcnode = run_get_node(DummyProcess, inputs_dict)

    return calcnode
