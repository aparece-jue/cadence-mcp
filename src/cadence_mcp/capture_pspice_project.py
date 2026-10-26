"""Bound project roles and immutable staging for native Capture PSpice input jobs.

This is an internal component, not a generic OPJ editor or a native completion claim.
"""
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import hashlib
import re

from .core import CadenceError, checked_path, sha256

SCOPE = 'same_directory_design_single_profile@1'


def fail(message):
    raise CadenceError('unsupported_pspice_project', message)


@dataclass(frozen=True)
class Node:
    items: tuple
    start: int
    end: int


def parse_project(text):
    if not isinstance(text, str) or len(text) > 1048576 or '\x00' in text:
        fail('Project text is missing, oversized or contains NUL.')
    tokens = []
    pos = 0
    while pos < len(text):
        if text[pos].isspace():
            pos += 1
            continue
        start = pos
        if text[pos] in '()':
            tokens.append((text[pos], text[pos], pos, pos + 1));pos += 1
        elif text[pos] == '"':
            pos += 1;value = []
            while pos < len(text) and text[pos] != '"':
                if text[pos] == '\\' and pos + 1 < len(text) and text[pos + 1] == '"':
                    value.append('"');pos += 2
                else:
                    value.append(text[pos]);pos += 1
            if pos == len(text):fail('Unterminated project string.')
            pos += 1
            if len(value) > 4096:fail('Project string exceeds limit.')
            tokens.append(('quoted', ''.join(value), start, pos))
        else:
            while pos < len(text) and not text[pos].isspace() and text[pos] not in '()"':pos += 1
            if pos == start or pos - start > 512:fail('Invalid or oversized project atom.')
            tokens.append(('bare', text[start:pos], start, pos))
        if len(tokens) > 50000:fail('Project token limit exceeded.')
    cursor = 0
    def node(depth):
        nonlocal cursor
        if depth > 64 or cursor >= len(tokens) or tokens[cursor][0] != '(':fail('Invalid project nesting.')
        start = tokens[cursor][2];cursor += 1;items = []
        if cursor >= len(tokens) or tokens[cursor][0] != 'bare':fail('Project node requires a bare tag.')
        while cursor < len(tokens) and tokens[cursor][0] != ')':
            token = tokens[cursor]
            if token[0] == '(':items.append(node(depth + 1))
            else:items.append(token[1]);cursor += 1
        if cursor >= len(tokens):fail('Unclosed project node.')
        end = tokens[cursor][3];cursor += 1
        return Node(tuple(items), start, end)
    tree = node(0)
    if cursor != len(tokens) or not tree.items or tree.items[0] != 'ExpressProject':fail('Expected one complete ExpressProject.')
    return tree


def walk(node):
    yield node
    for item in node.items:
        if isinstance(item, Node):yield from walk(item)


def relative_name(value):
    if not isinstance(value, str) or not value or len(value) > 512 or any(c in value for c in '\x00\r\n<>:"|?*'):
        fail('Project role requires a bounded relative Windows path.')
    raw = value.replace('\\', '/')
    if raw.startswith('./'):raw = raw[2:]
    parts = raw.split('/')
    if any(not p or p in ('.', '..') or p.endswith((' ', '.')) or re.fullmatch(r'(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', p, re.I) for p in parts):
        fail('Absolute, traversing or reserved project path.')
    return '/'.join(parts)


def singleton(nodes, tag):
    found = [n for n in nodes if n.items[0] == tag]
    if len(found) != 1 or len(found[0].items) != 2 or not isinstance(found[0].items[1], str):fail('Missing or ambiguous project field: ' + tag)
    return found[0].items[1]


def describe_project(project_bytes, profile_bytes, project_name):
    if not isinstance(project_bytes, bytes) or not isinstance(profile_bytes, bytes):fail('Project/profile inputs must be bytes.')
    try:
        if len(project_bytes) > 1048576 or len(profile_bytes) > 1048576:fail('Project/profile exceeds one MiB.')
        text = project_bytes.decode('utf-8-sig');profile = profile_bytes.decode('utf-8-sig')
    except (AttributeError, UnicodeError):
        raise CadenceError('unsupported_encoding', 'Project and profile metadata must be valid UTF-8.')
    project_name = relative_name(project_name)
    if '/' in project_name or Path(project_name).suffix.lower() != '.opj':fail('Project must have one OPJ filename.')
    tree = parse_project(text);nodes = list(walk(tree))
    allowed = {'ExpressProject', 'ProjectVersion', 'ProjectType', 'Folder', 'NoModify', 'File', 'Type',
               'BuildFileAddedOrDeleted', 'CompileFileAddedOrDeleted', 'PSPICE_Regenerate_Netlist_Flag',
               'DisplayName', 'ActiveProfile', 'Sort', 'DefaultLibraryBrowseDirectory', 'PartMRUSelector',
               'GlobalState', 'FileView', 'Path', 'HierarchyView', 'Doc', 'Frame', 'Placement', 'Tab',
               'Scroll', 'Zoom', 'Occurrence', 'Schematic', 'Page', 'MPSSessionName'}
    if any(n.items[0] not in allowed and n.items[0].casefold() != 'file.pspice.{09528990-3187-11d2-bc7b-00a0c90cbf91}' for n in nodes):
        fail('Unknown project nodes require explicit native-context support.')
    if len(tree.items) < 2 or not isinstance(tree.items[1], str) or tree.items[1].casefold() != Path(project_name).stem.casefold():fail('Project name does not match its filename.')
    files = [n for n in nodes if n.items[0] == 'File' or n.items[0].startswith('File.PSpice.')]
    roles = {'Schematic Design': [], 'PSpice Profile': [], 'Report': []}
    for n in files:
        if len(n.items) < 2 or not isinstance(n.items[1], str):fail('Invalid project file entry.')
        kind = singleton([x for x in n.items if isinstance(x, Node)], 'Type')
        if kind not in roles:fail('Additional project file roles require a dedicated resolver.')
        roles[kind].append(relative_name(n.items[1]))
    if len(roles['Schematic Design']) != 1 or len(roles['PSpice Profile']) != 1:fail('Exactly one design and one profile are currently required.')
    all_paths = [value.casefold() for values in roles.values() for value in values]
    if len(set(all_paths)) != len(all_paths):fail('Duplicate project file entries.')
    design = roles['Schematic Design'][0];selected = roles['PSpice Profile'][0]
    if '/' in design or Path(design).suffix.lower() != '.dsn' or Path(design).stem.casefold() != Path(project_name).stem.casefold():fail('Native export requires a same-directory, same-stem DSN.')
    parts = selected.split('/')
    if len(parts) != 3 or parts[0].casefold() != (Path(project_name).stem + '-PSpiceFiles').casefold() or Path(parts[2]).suffix.lower() != '.sim':fail('Unsupported profile directory layout.')
    active = relative_name(singleton(nodes, 'ActiveProfile'))
    if active.casefold() != selected.casefold():fail('Selected profile must be the unique active profile.')
    for n in nodes:
        if n.items[0] == 'Folder' and len(n.items) > 1 and n.items[1] in ('Model Libraries', 'Stimulus Files', 'Include Files', 'Library'):
            if any(not isinstance(x, Node) or x.items not in (('Sort', 'User'),) for x in n.items[2:]):fail('Additional library/stimulus/include resources need explicit snapshot support.')
    if not profile.startswith('@OrCAD Simulation Server Version:') or '\x00' in profile:fail('Expected bounded native simulation profile text.')
    sections = list(re.finditer(r'^@General:\s*\r?\n(.*?)^@End General\s*$', profile, re.M | re.S))
    if len(sections) != 1:fail('Expected one profile General section.')
    general = {}
    for key in ('ProfileName', 'ProfileFile', 'Connectivity', 'NetlistFile', 'DataFile', 'OutFile'):
        values = re.findall(r'^' + key + r'=\s*"([^"\r\n]*)"\s*$', sections[0][1], re.M)
        if len(values) != 1:fail('Missing or ambiguous profile field: ' + key)
        value = relative_name(values[0])
        if '/' in value:fail('Profile output fields must be simple filenames.')
        general[key] = value
    stem = Path(parts[2]).stem
    expected = {'ProfileName': stem, 'ProfileFile': parts[2], 'Connectivity': parts[1] + '.net', 'NetlistFile': stem + '.cir', 'DataFile': stem + '.dat', 'OutFile': stem + '.out'}
    if any(general[k].casefold() != value.casefold() for k, value in expected.items()):fail('Profile name, root, connectivity and output fields disagree.')
    parent = '/'.join(parts[:2]);net = parent + '/' + general['Connectivity']
    if any(value.casefold() != net.casefold() for value in roles['Report']):fail('Additional output reports require explicit staging support.')
    ui = [n for n in nodes if n.items[0] == 'GlobalState']
    top_ui = [n for n in tree.items if isinstance(n, Node) and n.items[0] == 'GlobalState']
    if len(ui) != len(top_ui) or len(ui) > 1:fail('Ambiguous UI restoration state.')
    ui_nodes = {id(n) for parent in ui for n in walk(parent)}
    ui_tags = {'FileView', 'Path', 'HierarchyView', 'Doc', 'Frame', 'Placement', 'Tab', 'Scroll', 'Zoom', 'Occurrence', 'Schematic', 'Page'}
    if any(n.items[0] in ui_tags and id(n) not in ui_nodes for n in nodes):fail('UI path/restoration nodes outside GlobalState are unsupported.')
    staged = text if not ui else text[:ui[0].start] + text[ui[0].end:]
    return {'scope': SCOPE, 'projectTarget': project_name, 'designTarget': design, 'profileTarget': selected,
            'rootName': parts[1], 'profileName': stem, 'netlistTarget': net,
            'aliasesTarget': str(PurePosixPath(net).with_suffix('.als')),
            'circuitTarget': parent + '/' + stem + '/' + general['NetlistFile'],
            'projectTransformation': 'utf8_drop_ui_global_state', 'stagedProjectSha256': hashlib.sha256(staged.encode('utf-8')).hexdigest()}, staged.encode('utf-8')


def freeze_project(config, capture, session_id, source_project, source_profile):
    project = checked_path(source_project, config.read_roots);profile = checked_path(source_profile, config.read_roots)
    if not project.is_file() or not profile.is_file():fail('Provide existing project and profile files.')
    for p in (project, profile):
        if p.stat().st_size > 1048576:fail('Project/profile exceeds one MiB.')
    before = {str(p): sha256(p) for p in (project, profile)}
    description, _ = describe_project(project.read_bytes(), profile.read_bytes(), project.name)
    declared = checked_path(str(project.parent / description['profileTarget']), config.read_roots)
    if declared != profile:fail('Explicit profile is not the project profile entry.')
    with capture.lock:
        session = capture._session(session_id)
        if sum(row['name'].casefold() == description['rootName'].casefold() for row in session['data']['schematic']) != 1:fail('Selected DSN has no unique profile root schematic.')
        design = checked_path(str(session['design']), (config.workspace_root,));revision = session['revision']
        sources = [{'role': 'design', 'path': str(design), 'sha256': revision},
                   {'role': 'project', 'path': str(project), 'sha256': before[str(project)]},
                   {'role': 'profile', 'path': str(profile), 'sha256': before[str(profile)]}]
        if design.stat().st_size > 32 * 1024 * 1024:fail('DSN exceeds 32 MiB.')
        capture._session(session_id)
    if any(sha256(Path(path)) != value for path, value in before.items()):raise CadenceError('source_changed', 'Project/profile changed during planning.')
    return {'description': description, 'sources': sources}


def validate_snapshot(config, snapshot):
    if not isinstance(snapshot, dict) or set(snapshot) != {'description', 'sources'}:fail('Invalid project snapshot shape.')
    sources = snapshot['sources']
    if not isinstance(sources, list) or any(not isinstance(r, dict) for r in sources) or [r.get('role') for r in sources] != ['design', 'project', 'profile']:fail('Invalid project snapshot roles.')
    paths = {}
    for row in sources:
        if set(row) != {'role', 'path', 'sha256'} or not isinstance(row['sha256'], str) or not re.fullmatch('[a-f0-9]{64}', row['sha256']):fail('Invalid project source identity.')
        p = checked_path(row['path'], (config.workspace_root,) if row['role'] == 'design' else config.read_roots)
        if not p.is_file() or p.stat().st_size > (32 * 1024 * 1024 if row['role'] == 'design' else 1048576):fail('Invalid source size/type.')
        if sha256(p) != row['sha256']:raise CadenceError('source_changed', 'A frozen project input changed.')
        paths[row['role']] = p
    description, staged = describe_project(paths['project'].read_bytes(), paths['profile'].read_bytes(), paths['project'].name)
    if description != snapshot['description'] or checked_path(str(paths['project'].parent / description['profileTarget']), config.read_roots) != paths['profile']:fail('Project snapshot roles or description were changed.')
    return paths, staged


def stage_snapshot(config, snapshot, directory):
    directory = checked_path(str(directory), (config.workspace_root,));paths, project_bytes = validate_snapshot(config, snapshot)
    target_root = directory / 'project'
    if target_root.exists() or target_root.is_symlink():raise CadenceError('preexisting_native_input', 'Native task project directory already exists; never overwrite or merge it.')
    target_root.mkdir();checked_path(str(target_root), (directory,));result = {}
    for role in ('project', 'design', 'profile'):
        target = checked_path(str(target_root / snapshot['description'][role + 'Target']), (target_root,), exists=False)
        target.parent.mkdir(parents=True, exist_ok=True);target = checked_path(str(target), (target_root,), exists=False)
        raw = project_bytes if role == 'project' else paths[role].read_bytes()
        with target.open('xb') as stream:stream.write(raw)
        wanted = snapshot['description']['stagedProjectSha256'] if role == 'project' else next(row['sha256'] for row in snapshot['sources'] if row['role'] == role)
        if sha256(target) != wanted:raise CadenceError('target_changed', 'Staged project input does not match its frozen bytes.')
        result[role] = str(target)
    validate_snapshot(config, snapshot)
    return result
