"""Versioned scope-limited release surface; development tools are registered separately."""
from functools import wraps
import inspect
from typing import Literal
from pydantic_core import PydanticUndefined
from .core import CadenceError,failure

GROUPS={
 'environment':('cadence_get_environment','cadence_get_capabilities'),
 'definitions':('cadence_create_workspace','capture_open','capture_query','capture_snapshot','capture_close','capture_get_part_properties','capture_get_property_layers'),
 'library_read':('capture_library_open','capture_library_query','capture_library_close'),
 'property_write':('capture_plan_property','capture_apply_property','capture_property_jobs','capture_cancel_property','capture_recover_property','capture_open_edit_result'),
 'gui_host':('capture_gui_instances','capture_gui_attach','capture_gui_query','capture_gui_detach','capture_gui_status','capture_gui_diagnose'),
 'editor_wire':('capture_plan_wire_add','capture_apply_wire_add','capture_wire_add_jobs','capture_cancel_wire_add','capture_recover_wire_add','capture_plan_wire_edit','capture_apply_wire_edit','capture_wire_edit_jobs','capture_cancel_wire_edit','capture_recover_wire_edit','capture_query_connections','capture_compare_connections','capture_check_wiring'),
 'ordinary_bus':('capture_query_bus','capture_plan_bus_create','capture_apply_bus_create','capture_bus_create_jobs','capture_cancel_bus_create','capture_recover_bus_create'),
 'simulation_input':('pspice_prepare','pspice_get_input','pspice_close_input','pspice_plan_input_check','pspice_apply_input_check','pspice_input_check_jobs','pspice_cancel_input_check','pspice_recover_input_check','pspice_inspect_input_check'),
 'engine_runs':('pspice_plan_run','pspice_apply_run','pspice_run_jobs','pspice_cancel_run','pspice_recover_run','pspice_open_run_dat','pspice_inspect_run_output','pspice_inspect_run_failure'),
 'analog_results':('pspice_dat_query','pspice_dat_samples','pspice_dat_measure','pspice_dat_close','pspice_inspect_output'),
}
TOOLS=frozenset(name for names in GROUPS.values() for name in names)
LIMITS={
 'pspice_prepare':dict(inputEncoding=Literal['utf-8'],inputBudget=Literal['standard']),
 'capture_query_connections':dict(entity=Literal['wire','alias']),
 'capture_plan_wire_add':dict(guiSessionId=str,hostProject=str),
 'capture_plan_wire_edit':dict(guiSessionId=str,hostProject=str,operation=Literal['delete']),
 'capture_open_edit_result':dict(kind=Literal['property','wire_add','wire_edit','bus_create']),
 'capture_gui_attach':dict(access=Literal['read']),
 'pspice_open_run_dat':dict(backend=Literal['engine']),
 'pspice_inspect_run_output':dict(backend=Literal['engine']),
 'pspice_inspect_run_failure':dict(kind=Literal['engine','input_check']),
}
NOTES={
 'capture_plan_wire_add':'Validated release: explicit guiSessionId/hostProject required; standalone Dbo construction is excluded.',
 'capture_plan_wire_edit':'Validated release: native editor deletion only, explicit guiSessionId/hostProject required. Endpoint edits are excluded.',
 'capture_open_edit_result':'Validated release accepts only property, native-editor wire_add/wire_edit, and ordinary bus_create results.',
}
def guard(name,args,tasks):
    if name=='pspice_prepare' and (args.get('inputEncoding','utf-8')!='utf-8' or args.get('inputBudget','standard')!='standard'):raise CadenceError('release_scope_unavailable','This release supports standard-budget explicit UTF-8 CIR inputs.')
    if name=='capture_query_connections' and args.get('entity') not in ('wire','alias'):raise CadenceError('release_scope_unavailable','Only verified wire/alias inventory is supported by this release profile.')
    if name in ('capture_plan_wire_add','capture_plan_wire_edit'):
        if not args.get('guiSessionId') or not args.get('hostProject'):raise CadenceError('release_scope_unavailable','Validated wire workflows require an explicit native editor host.')
    if name=='capture_plan_wire_edit' and args.get('operation')!='delete':raise CadenceError('release_scope_unavailable','Validated wire edit supports native editor deletion only.')
    if name in ('pspice_open_run_dat','pspice_inspect_run_output') and args.get('backend','engine')!='engine':raise CadenceError('release_scope_unavailable','CLI tasks are outside this release profile.')
    if name=='pspice_inspect_run_failure' and args.get('kind','engine') not in ('engine','input_check'):raise CadenceError('release_scope_unavailable','Only engine/input-check diagnostics are supported here.')
    if name=='capture_gui_attach' and args.get('access','read')!='read':raise CadenceError('release_scope_unavailable','Experimental GUI note-write access is excluded.')
    kind=None
    if name in ('capture_apply_wire_add','capture_recover_wire_add'):kind='wire_add'
    if name in ('capture_apply_wire_edit','capture_recover_wire_edit'):kind='wire_edit'
    if name=='capture_open_edit_result':
        kind=args['kind']
        if kind not in ('property','wire_add','wire_edit','bus_create'):raise CadenceError('release_scope_unavailable','This edit kind is outside the validated profile.')
    if kind in ('wire_add','wire_edit'):
        _,_,row=tasks[kind]._load(args['planId']);payload=row['plan']['payload']
        if not payload.get('editorHost') or (kind=='wire_edit' and payload.get('operation')!='delete'):raise CadenceError('release_scope_unavailable','Legacy standalone wire plans cannot be applied, recovered or opened in this profile.')

def protect(fn,tasks,packed):
    signature=inspect.signature(fn)
    @wraps(fn)
    async def validated(*args,**kwargs):
        try:
            bound=signature.bind(*args,**kwargs);bound.apply_defaults();guard(fn.__name__,bound.arguments,tasks)
        except CadenceError as error:return packed(failure(error))
        return await fn(*args,**kwargs)
    validated.__doc__=(fn.__doc__ or '')+' '+NOTES.get(fn.__name__,'Scope-limited validated release profile; occurrence/Bundle/DRC and CLI completeness are not certified.')
    return validated

def narrow_schema(tool):
    for name,annotation in LIMITS.get(tool.name,{}).items():
        field=tool.fn_metadata.arg_model.model_fields[name];field.annotation=annotation
        if name in ('guiSessionId','hostProject'):field.default=PydanticUndefined

def capabilities():
    return dict(releaseProfile='validated-v0.1',toolCount=len(TOOLS),tools=sorted(TOOLS),supportedGroups={k:list(v) for k,v in GROUPS.items()},writesRequirePlan=True,writeTargets='isolated_copies_with_explicit_expectations',features={
      'capture.definition_query':'validated_definition_scope','capture.property_layers':'validated_definition_scope','capture.olb':'validated_read_only',
      'capture.isolated_property_edit':'validated_approved_fields','capture.editor_wire_add':'validated_explicit_host_and_pin_oracle',
      'capture.editor_wire_delete':'validated_explicit_host_delete_only','capture.bus_inventory':'validated_ordinary_bus_and_same_page_native_pin_membership',
      'capture.bus_create':'validated_2_to_128_vertical_ordinary_bus','pspice.prepare':'validated_explicit_reference_subset',
      'pspice.input_check':'validated_setup_only','pspice.run':'validated_independent_engine_explicit_CIR','pspice.dat':'validated_verified_engine_analog_results'},
      excluded=['CLI execution and parameter STEP','Capture profile/netlist generation','nested Bundle','flat occurrence connectivity','native DRC automation','PDF automation','Allegro','digital DAT and DAT export','unverified graphics/cache/placement branches'],fullDevelopmentGates=dict(passed=6,total=34),fullProjectComplete=False)
