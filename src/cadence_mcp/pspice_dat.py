"""Immutable imported DAT sessions using fixed native PSpice data operations."""
from pathlib import Path
import json
import math
import re
import shutil
import threading

from .core import CadenceError, checked_path, new_id, sha256, write_json
from .environment import process_env, ADAPTERS, FILES
from .process_tree import run_owned_process


def unit_for(name, axis):
    if name == axis and name in ('Time', 'Frequency'):
        return {'unit': {'Time':'s', 'Frequency':'Hz'}[name], 'unitSource':'axis_name_convention'}
    for prefix, unit in [('V(', 'V'), ('I(', 'A'), ('W(', 'W')]:
        if name.upper().startswith(prefix) and name.endswith(')'):
            return {'unit':unit, 'unitSource':'trace_name_convention'}
    return {'unit':None, 'unitSource':'unknown'}


def decode_headers(raw):
    try:
        if set(raw) != {'blockCount', 'headerJSON'} or type(raw['blockCount']) is not int or not 1 <= raw['blockCount'] <= 128:
            raise ValueError('block count')
        rows = json.loads(raw['headerJSON'])
        if not isinstance(rows,list) or len(rows) != raw['blockCount']:
            raise ValueError('block array')
        blocks, traces = [], {}
        total = 0
        for index, row in enumerate(rows):
            if not isinstance(row,dict) or type(row.get('Number')) is not int or row['Number'] != index:
                raise ValueError('block identity')
            for name, low, high in [('ComplexFlag',1,2),('DataType',0,2),('NumberofAnalogRows',0,100000),('NumberofAnalogColumns',0,10000)]:
                if type(row.get(name)) is not int or not low <= row[name] <= high: raise ValueError(name)
            axis = row.get('PrimaryParamName');analysis = row.get('AnalysisName')
            if not isinstance(axis,str) or not axis or len(axis)>512 or not isinstance(analysis,str): raise ValueError('axis/analysis')
            digital_keys = ('NumberofDigitalRows','NumberofDigitalColumns')
            digital_complete = all(key in row for key in digital_keys)
            if any(key in row for key in digital_keys) and not digital_complete: raise ValueError('partial digital counts')
            digital_rows = row.get('NumberofDigitalRows',0);digital_columns = row.get('NumberofDigitalColumns',0)
            if type(digital_rows) is not int or not 0<=digital_rows<=100000 or type(digital_columns) is not int or not 0<=digital_columns<=10000: raise ValueError('digital bounds')
            if row['DataType']==0 and (digital_rows or digital_columns): raise ValueError('analog block has digital counts')
            if row['DataType']==1 and (not digital_complete or row['NumberofAnalogRows'] or row['NumberofAnalogColumns']): raise ValueError('digital block counts')
            groups = row.get('Trace Names',{})
            if not isinstance(groups,dict): raise ValueError('trace groups')
            analog_supported = row['DataType']==0 or (row['DataType']==2 and digital_complete and row['NumberofAnalogColumns']>0)
            digital_supported=digital_complete and digital_rows>0 and digital_columns>0 and axis=="Time" and analysis=="Transient Analysis"
            table, ownership = [], {}
            for kind,key,count in [('analog','Analog Names',row['NumberofAnalogColumns']),('digital','Digital Names',digital_columns)]:
                names=groups.get(key,[])
                if not isinstance(names,list) or len(names)!=count: raise ValueError('trace count')
                for item in names:
                    if isinstance(item,str): name, aliases = item, []
                    elif isinstance(item,dict) and len(item)==1: name, aliases = next(iter(item.items()))
                    else: raise ValueError('trace shape')
                    if not isinstance(aliases,list) or any(not isinstance(a,str) for a in aliases): raise ValueError('aliases')
                    if not isinstance(name,str) or not name or len(name)>512 or any(c in name for c in '\x00\r\n'): raise ValueError('name')
                    aliases=list(dict.fromkeys(a for a in aliases if a!=name))
                    for token in [name,*aliases]:
                        if not token or len(token)>512 or any(c in token for c in '\x00\r\n'): raise ValueError('alias')
                        if token in ownership: raise ValueError('ambiguous trace')
                        ownership[token]=name
                    trace={'name':name,'aliases':aliases,**(unit_for(name,axis) if kind=='analog' else {'unit':None,'unitSource':'digital_logic_not_physical_quantity'})}
                    if row['DataType']!=0:
                        trace.update(signalType=kind,sampleReadSupported=analog_supported if kind=='analog' else digital_supported,rowCount=row['NumberofAnalogRows'] if kind=='analog' else digital_rows)
                    if kind=='digital':trace.update(rowCountSource='block_header_not_per_trace_record_count',digitalReadScope='unflagged_getDigital_change_records_v1' if digital_supported else None)
                    table.append(trace)
            total += sum(1+len(t['aliases']) for t in table)
            if total>100000: raise ValueError('trace limit')
            analog_table=table[:row['NumberofAnalogColumns']]
            if row['NumberofAnalogColumns'] and sum(t['name']==axis or axis in t['aliases'] for t in analog_table)!=1: raise ValueError('missing analog axis')
            if row['DataType']==0 and not row['NumberofAnalogColumns']: raise ValueError('missing axis')
            block={'index':index,'analysisName':analysis,'axis':axis,'rowCount':row['NumberofAnalogRows'] if row['DataType']!=1 else digital_rows,
                   'traceCount':len(table),'complex':row['ComplexFlag']==2,'dataTypeCode':row['DataType'],
                   'analogReadSupported':analog_supported}
            if row['DataType']!=0:
                block.update(analogRowCount=row['NumberofAnalogRows'],analogTraceCount=row['NumberofAnalogColumns'],
                             digitalMetadataComplete=digital_complete,digitalReadSupported=digital_supported,
                             digitalReadScope='unflagged_getDigital_change_records_v1' if digital_supported else None,
                             digitalRowCount=digital_rows if digital_complete else None,digitalTraceCount=digital_columns if digital_complete else None)
            blocks.append(block);traces[index]=table
        return blocks, traces
    except (ValueError,KeyError,TypeError,AttributeError) as error:
        raise CadenceError('invalid_dat_metadata','Native DAT metadata has an unsupported or inconsistent shape.','decode') from error


def decode_samples(raw, block, trace):
    try:
        if set(raw) != {'block','trace','rows','valuesCSV'} or type(raw['block']) is not int or raw['block'] != block['index'] or raw['trace'] != trace or type(raw['rows']) is not int or raw['rows'] != block['rowCount'] or not isinstance(raw['valuesCSV'],str):
            raise ValueError('trace receipt')
        tokens = raw['valuesCSV'].split(',') if raw['valuesCSV'] else []
        width = 2 if block['complex'] else 1
        if len(tokens) != block['rowCount']*width: raise ValueError('row count')
        values = []
        for token in tokens:
            if not re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?',token.strip()): raise ValueError('numeric token')
            value = float(token)
            if not math.isfinite(value): raise ValueError('finite')
            values.append(value)
        return [{'index':i,'real':values[i*width],'imaginary':values[i*width+1] if width==2 else None}
                for i in range(block['rowCount'])]
    except (ValueError,KeyError,TypeError) as error:
        raise CadenceError('invalid_dat_samples','Native DAT samples do not match the declared finite real/complex rows.','decode') from error


def legacy_header(raw):
    """Recognize only the observed legacy representation; never repair its JSON."""
    return (isinstance(raw,dict) and set(raw)=={'blockCount','headerJSON'}
            and isinstance(raw['headerJSON'],str) and raw['headerJSON'].lstrip().startswith('{')
            and all(token in raw['headerJSON'] for token in ('"Analog Traces"','"Sweep Data"','"Number Of Analog Rows"')))


class PSpiceDat:
    def __init__(self,config):
        self.config=config
        self.sessions={}
        self.lock=threading.RLock()

    def _worker(self,directory,mode,block=0,trace=''):
        output=directory / (new_id('read')+'.json')
        argv=[str(self.config.install_root/FILES['tclsh']),str(ADAPTERS/('inspect_digital_dat.tcl' if mode=='digital_trace' else 'inspect_dat.tcl')),str(self.config.install_root),
              str(directory/'imported.dat'),str(output),mode,str(block),trace,str(ADAPTERS/'json.tcl')]
        process=run_owned_process(argv,directory,process_env(self.config),self.config.timeout_seconds)
        write_json(directory/(new_id('process')+'.json'),process)
        if process['state']!='exited' or process['returnCode']!=0:
            raise CadenceError('dat_worker_failed','Native DAT reader did not finish successfully; evidence retained.','worker')
        try:
            if output.stat().st_size>32*1024*1024: raise ValueError('size')
            data=json.loads(output.read_text(encoding='utf-8'))
            if not isinstance(data,dict):raise ValueError('shape')
        except (OSError,ValueError) as error:
            raise CadenceError('invalid_dat_result','Native reader produced no bounded DAT result.','decode') from error
        # Keep bounded raw receipts for decode/validation failures and audit.
        return data

    def open(self,source_dat):
        with self.lock:
            if len(self.sessions)>=32:raise CadenceError('session_limit','At most 32 imported DAT sessions per server.')
            source=checked_path(source_dat,self.config.read_roots)
            if not source.is_file() or source.suffix.lower()!='.dat':raise CadenceError('unsupported_input','Provide one DAT file from configured read roots.')
            if source.stat().st_size>32*1024*1024:raise CadenceError('input_limit','DAT exceeds 32 MiB.')
            before=sha256(source)
            ident=new_id('dat'); directory=self.config.workspace_root/ident; directory.mkdir()
            directory=checked_path(str(directory),(self.config.workspace_root,))
            target=directory/'imported.dat'; shutil.copyfile(source,target)
            if target.stat().st_size>32*1024*1024:raise CadenceError('input_limit','Copied DAT exceeds 32 MiB.')
            if sha256(source)!=before or sha256(target)!=before:raise CadenceError('source_changed','DAT changed during import.')
            raw=self._worker(directory,'headers');header_source='native_json'
            try:blocks,traces=decode_headers(raw)
            except CadenceError:
                if not legacy_header(raw):raise
                # Query documented native fields/names independently. No permissive JSON parser.
                blocks,traces=decode_headers(self._worker(directory,'headers_direct'))
                header_source='native_direct_headers'
            if sha256(target)!=before:raise CadenceError('target_changed','DAT changed during native reading.')
            manifest={'datId':ident,'sourcePath':str(source),'revision':before,'provenance':'imported_file',
                      'blockCount':len(blocks),'jobAssociationVerified':False,'solverSuccessVerified':False,
                      'headerSource':header_source,'aliasGroupingSource':'native_json' if header_source=='native_json' else 'native_direct_digital_semicolon_groups' if any(b['dataTypeCode']!=0 for b in blocks) else 'not_available_from_direct_names'}
            write_json(directory/'manifest.json',manifest)
            write_json(directory/'metadata.json',{'blocks':blocks,'traces':traces})
            self.sessions[ident]={'directory':directory,'manifest':manifest,'blocks':blocks,'traces':traces}
            return manifest

    def _session(self,ident):
        if ident not in self.sessions:raise CadenceError('session_lost','DAT session is closed or belongs to another server.')
        session=self.sessions[ident]
        directory=checked_path(str(session['directory']),(self.config.workspace_root,))
        target=checked_path(str(directory/'imported.dat'),(directory,))
        if sha256(target)!=session['manifest']['revision']:raise CadenceError('target_changed','Imported DAT snapshot is stale.')
        return session

    @staticmethod
    def _block(session,index):
        if type(index) is not int or not 0<=index<len(session['blocks']):raise CadenceError('invalid_block','DAT block index is outside this session.')
        return session['blocks'][index]

    @staticmethod
    def _page(rows,offset,limit):
        if type(offset) is not int or type(limit) is not int or not 0<=offset<=len(rows) or not 1<=limit<=1000:
            raise CadenceError('invalid_query','Invalid DAT offset or page size.')
        end=min(offset+limit,len(rows))
        return {'items':rows[offset:end],'total':len(rows),'nextOffset':end if end<len(rows) else None,'complete':end==len(rows)}

    def query(self,ident,entity,block=None,offset=0,limit=100):
        with self.lock:
            session=self._session(ident)
            if entity=='block':
                if block is not None:raise CadenceError('invalid_query','Block listing does not accept a block selector.')
                rows=session['blocks']
            elif entity=='trace':
                self._block(session,block);rows=session['traces'][block]
            else:raise CadenceError('invalid_query','DAT entity must be block or trace.')
            return {**self._page(rows,offset,limit),'revision':session['manifest']['revision'],'provenance':session['manifest']['provenance']}

    def _all_samples(self,ident,block,trace):
        session=self._session(ident);selected=self._block(session,block)
        if not selected['analogReadSupported']:raise CadenceError('capability_unavailable','This block has no validated analog sample path; logic samples require a dedicated reader.')
        matches=[t for t in session['traces'][block] if trace==t['name'] or trace in t['aliases']]
        if len(matches)!=1:raise CadenceError('trace_not_found','Exact DAT trace name or alias is missing or ambiguous.')
        if matches[0].get('signalType','analog')!='analog' or not matches[0].get('sampleReadSupported',True):raise CadenceError('capability_unavailable','Digital logic samples are not decoded by the analog path.')
        canonical=matches[0]['name'];raw=self._worker(session['directory'],'trace',block,canonical)
        self._session(ident);return session,selected,canonical,decode_samples(raw,selected,canonical)

    def samples(self,ident,block,trace,offset=0,limit=1000):
        with self.lock:
            session=self._session(ident);selected=self._block(session,block)
            self._page(range(selected['rowCount']),offset,limit)
            session,selected,canonical,rows=self._all_samples(ident,block,trace)
            return {**self._page(rows,offset,limit),'block':block,'trace':canonical,'requestedTrace':trace,
                    'complex':selected['complex'],**unit_for(canonical,selected['axis']),
                    'revision':session['manifest']['revision'],'jobAssociationVerified':session['manifest'].get('jobAssociationVerified',False),'producedByPlan':session['manifest'].get('producedByPlan')}

    def digital_samples(self,ident,block,trace,offset=0,limit=1000):
        from .pspice_digital import decode_digital_records,SCOPE
        with self.lock:
            session=self._session(ident);selected=self._block(session,block)
            if not selected.get('digitalReadSupported'):raise CadenceError('capability_unavailable','Dedicated digital records require complete positive-row transient metadata.')
            self._page(range(selected['digitalRowCount']),offset,limit)
            matches=[t for t in session['traces'][block] if t.get('signalType')=='digital' and (trace==t['name'] or trace in t['aliases'])]
            if len(matches)!=1:raise CadenceError('trace_not_found','Exact digital canonical name or alias is missing; axes and analog names are not sent to the digital reader.')
            canonical=matches[0]['name'];raw=self._worker(session['directory'],'digital_trace',block,canonical)
            self._session(ident);rows=decode_digital_records(raw,selected,canonical)
            return {**self._page(rows,offset,limit),'block':block,'trace':canonical,'requestedTrace':trace,
                    'blockDigitalRows':selected['digitalRowCount'],'rowCountSource':'native_per_trace_change_records',
                    'timeUnit':'s','timeUnitSource':'axis_name_convention','signalType':'digital','digitalReadScope':SCOPE,
                    'strengthEncoding':'native_integer_0_to_63','strengthResistanceMappingVerified':False,
                    'nativeOpaqueTailReturned':False,'nativeOpaqueTailSemanticsVerified':False,
                    'nativeFlaggedStatesSupported':False,'probeDisplayInterpretationVerified':False,
                    'revision':session['manifest']['revision'],'provenance':session['manifest']['provenance'],
                    'jobAssociationVerified':session['manifest'].get('jobAssociationVerified',False),'producedByPlan':session['manifest'].get('producedByPlan')}

    def measure(self,ident,block,trace,measurement='summary',component='real',at_axis=None,threshold=None,direction='either'):
        from .pspice_measure import validate_measurement,measure_samples
        validate_measurement(measurement,component,at_axis,threshold,direction)
        with self.lock:
            session=self._session(ident);selected=self._block(session,block)
            matches=[t for t in session['traces'][block] if trace==t['name'] or trace in t['aliases']]
            if len(matches)!=1:raise CadenceError('trace_not_found','Exact DAT trace name or alias is missing or ambiguous.')
            if matches[0].get('signalType','analog')!='analog' or not selected['analogReadSupported']:raise CadenceError('capability_unavailable','Logic or unverified mixed metadata cannot be measured as analog data.')
            _,_,_,axis=self._all_samples(ident,block,selected['axis'])
            session,selected,canonical,values=self._all_samples(ident,block,trace)
            result=measure_samples(axis,values,measurement,component,at_axis,threshold,direction)
            self._session(ident)
            return {**result,'datId':ident,'block':block,'trace':canonical,'axis':selected['axis'],
                    'valueUnits':unit_for(canonical,selected['axis']),'axisUnits':unit_for(selected['axis'],selected['axis']),
                    'revision':session['manifest']['revision'],'provenance':session['manifest']['provenance'],
                    'jobAssociationVerified':session['manifest'].get('jobAssociationVerified',False),'producedByPlan':session['manifest'].get('producedByPlan'),
                    'notChecked':['between_sample_behavior','discontinuities','native_measure_directives','electrical_design_safety']}

    def close(self,ident):
        with self.lock:
            if ident not in self.sessions:raise CadenceError('session_lost','DAT session is closed or unknown.')
            del self.sessions[ident]
            return {'datId':ident,'closed':True,'evidenceRetained':True}
