"""Native-checked global library selection from an explicit INI byte snapshot.

Supports the original single-library-path/no-local-overlays configuration.
Does not infer general INI semantics, stimulus handling or encrypted-model safety.
"""
import configparser,json,re,uuid
from pathlib import Path
from .core import CadenceError,checked_path,sha256,write_json
from .environment import ADAPTERS,process_env
from .process_tree import run_owned_process
from .pspice_input import REFERENCE,ARGUMENT

KEYS={'Libpath','GlobalLibs','LocalLibs','ProfileLibs','GlobalIncs','LocalIncs','ProfileIncs','GlobalStms','LocalStms','ProfileStms'}
def fail(message):raise CadenceError('unsupported_inherited_configuration',message)

def decode_selection(ini_text,before,after,read_roots):
    if not isinstance(before,dict) or not isinstance(after,dict) or set(before)!=KEYS or set(after)!=KEYS:fail('Unknown native configuration fields.')
    if any(not isinstance(v,str) if k=='Libpath' else not isinstance(v,list) or any(not isinstance(x,str) for x in v) for d in (before,after) for k,v in d.items()):fail('Native configuration field type differs.')
    if any(before[k] for k in KEYS):fail('Profile has native configuration overlays; preserve them with a dedicated merged-role resolver.')
    if any(after[k] for k in KEYS-{'Libpath','GlobalLibs'}):fail('Non-global-library configuration requires additional role support.')
    # Native Windows INI files may contain unrelated empty section names.
    # Preserve the full byte snapshot; parse only the section whose semantics we prove.
    selected=[];active=False;matches=0
    for line in ini_text.splitlines():
        header=re.fullmatch(r'\s*\[([^\]]*)\]\s*(?:;.*)?',line)
        if header:
            active=header[1].casefold()=='pspice netlist'
            if active:matches+=1
        if active:selected.append(line)
    if matches!=1:fail('Exactly one PSPICE NETLIST section is required.')
    parser=configparser.RawConfigParser(strict=True,interpolation=None)
    try:parser.read_string('\n'.join(selected))
    except configparser.Error as error:raise CadenceError('unsupported_inherited_configuration','Ambiguous or invalid source INI.') from error
    sections=[x for x in parser.sections() if x.casefold()=='pspice netlist']
    if len(sections)!=1:fail('Exactly one PSPICE NETLIST section is required.')
    lines=[]
    for key,value in parser.items(sections[0]):
        if not re.fullmatch(r'line[1-9][0-9]{0,2}',key):fail('Unknown PSPICE NETLIST key.')
        lines.append((int(key[4:]),value))
    lines.sort();names=[]
    if not 1<=len(lines)<=16:fail('Use one to sixteen global library lines.')
    for _,line in lines:
        match=REFERENCE.fullmatch(line);arg=ARGUMENT.fullmatch(match[2]) if match else None
        if not match or match[1].upper()!='LIB' or not arg:fail('Global non-library directives require dedicated configuration support.')
        name=next(x for x in arg.groups() if x is not None)
        if any(x in name for x in ('*','?','%','$','{','}','\x00','\r','\n')):fail('Dynamic global library names are unsupported.')
        names.append(name)
    # Bind the native list to the exact original INI entries; do not strip arbitrary wildcards.
    if after['GlobalLibs']!=[x+'*' for x in names]:fail('Native enabled-library list/order differs from literal INI entries.')
    path=after['Libpath']
    if path.startswith('"') and path.endswith('"'):path=path[1:-1]
    if not path or any(c in path for c in ('"',';','\x00','\r','\n')):fail('Only one unambiguous native-resolved library directory is currently supported.')
    directory=checked_path(path,read_roots)
    if not directory.is_dir():fail('Native library path is not a directory.')
    resolved=[]
    for name in names:
        candidate=Path(name)
        if not candidate.is_absolute():
            if candidate.name!=name:fail('Relative library subdirectories require explicit search-order support.')
            candidate=directory/candidate
        target=checked_path(str(candidate),read_roots)
        if not target.is_file():fail('Native-selected global library is missing.')
        resolved.append(str(target))
    return resolved

def inspect_global_selection(config,netdir,description,source_ini):
    ini=checked_path(source_ini,config.read_roots)
    if not ini.is_file() or ini.stat().st_size>1048576:fail('Source INI is missing or oversized.')
    raw=ini.read_bytes();ini_hash=sha256(ini)
    try:text=raw.decode('utf-8-sig')
    except UnicodeError as error:raise CadenceError('unsupported_encoding','Source INI must be UTF-8/ASCII.') from error
    root=config.workspace_root/('profile-config-query-'+uuid.uuid4().hex);root.mkdir();sources={str(ini):ini_hash}
    for role in ('project','design','profile'):
        relative=description[role+'Target'];source=checked_path(str(netdir/'project'/relative),(netdir,));sources[str(source)]=sha256(source)
        target=checked_path(str(root/'project'/relative),(root,),exists=False);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(source.read_bytes())
        if sha256(target)!=sources[str(source)]:raise CadenceError('source_changed','Configuration query input changed while copying.')
    private=root/'selected.ini';private.write_bytes(raw)
    if sha256(private)!=ini_hash or sha256(ini)!=ini_hash:raise CadenceError('source_changed','Source INI changed while freezing.')
    output=root/'native-result.json'
    process=run_owned_process([config.install_root/'tcltk/bin/tclsh.exe',ADAPTERS/'profile_configuration_query.tcl',config.install_root,
             root/'project'/description['projectTarget'],root/'project'/description['profileTarget'],private,output],root,process_env(config),config.timeout_seconds)
    if not output.is_file() or output.stat().st_size>3*1048576:fail('Native configuration result is missing/oversized.')
    try:
        result=json.loads(output.read_text(encoding='utf-8'));before=json.loads(result['beforeJSON'])['ConfigFiles'];after=json.loads(result['afterJSON'])['ConfigFiles']
    except (KeyError,ValueError,TypeError) as error:raise CadenceError('unsupported_inherited_configuration','Native merged configuration is incomplete.') from error
    if (process['state']!='exited' or process['returnCode']!=0 or process['remainingOwnedProcesses']!=0 or process.get('rootExitSignalConfirmed') is not True
        or process.get('observedProcessExitSignalsConfirmed') is not True or type(result.get('pid')) is not int or result['pid']!=process['pid']
        or result.get('returned') is not True or result.get('loadResult')!='0' or result.get('libincResult')!='0'):fail('Native merged configuration call did not finish successfully.')
    if any(sha256(Path(path))!=value for path,value in sources.items()):raise CadenceError('source_changed','Configuration source changed during native query.')
    selected=decode_selection(text,before,after,config.read_roots)
    record={'sourceIni':str(ini),'sourceIniSha256':ini_hash,'snapshotDirectory':str(root),'selectedIniSha256':sha256(private),
            'nativeResultSha256':sha256(output),'nativeConfigFilesBefore':before,'nativeConfigFilesAfter':after,'selectedLibraries':selected,
            'scope':'native_checked_global_libraries_single_search_directory@1'}
    write_json(root/'configuration-proof.json',record)
    return {**record,'proofSha256':sha256(root/'configuration-proof.json')}
