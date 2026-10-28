"""MCP stdio entry point. Cadence and project roots are host configuration."""
from __future__ import annotations

import argparse
import asyncio
import contextvars
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any, Literal
import json

from mcp.server import MCPServer
from mcp.server.mcpserver.tools.base import Tool
from mcp.types import CallToolResult, TextContent, ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from . import __version__
from .core import CadenceError, Config, failure, result
from .capture import CaptureService
from .capture_edit import CapturePropertyEdits
from .capture_pspice_netlist import CapturePSpiceNetlists
from .capture_wire import CaptureWireAdds
from .capture_bus import query_bus
from .capture_bus_create import CaptureBusCreates
from .editor_wire_host import EditorWireHost
from .capture_wire_edit import CaptureWireEdits
from .capture_graphic_line import CaptureGraphicLines
from .capture_graphic_text import CaptureGraphicTexts,GraphicTextChange
from .capture_part_vectors import query_part_vectors
from .capture_symbol_contacts import check_symbol_contacts
from .capture_page_bounds import query_page_dimensions,check_page_graphic_bounds
from .capture_part_edit import CapturePartEdits
from .capture_alias_edit import CaptureAliasEdits
from .capture_net_symbol_edit import CaptureNetSymbolEdits
from .capture_nc import CaptureNcEdits
from .capture_hierarchy_edit import CaptureHierarchyEdits
from .capture_references import CaptureReferenceEdits
from .capture_design_create import CaptureDesignCreates
from .capture_place import CapturePlacements
from .capture_multiunit_place import CaptureMultiunitPlacements
from .capture_cache import query_cache
from .capture_cache_bindings import query_cache_binding
from .capture_cache_replace import CaptureCacheReplacements
from .capture_user_properties import CaptureUserProperties
from .capture_display_properties import CaptureDisplayProperties
from .capture_display_fonts import CaptureDisplayFonts,query_font
from .capture_page_vectors import query_page_vectors
from .capture_occurrence_properties import query_occurrence_properties
from .library_vectors import VectorFont
from .capture_net_symbol_create import CaptureNetSymbolCreates
from .net_symbols import query_net_symbols
from .library import LibraryService
from .library_create import LibraryCreates
from .library_vectors import LibraryVector,LibraryCreationVector,BitmapGeometry
from .library_vector_query import query_library_vectors
from .library_edit import LibraryPinEdits
from .library_vector_edit import LibraryVectorEdits
from .library_package_edit import LibraryPackageEdits,query_package_properties
from .pspice_library_metadata import inspect_library_metadata
from .pspice_input import PSpiceInputs
from .pspice_input_checks import PSpiceInputChecks
from .pspice_dat import PSpiceDat
from .pspice_runs import PSpiceRuns
from .pspice_cli_runs import PSpiceCliRuns
from .pspice_profile_circuits import PSpiceProfileCircuits
from .pspice_exports import PSpiceExports
from .pspice_measurements import PSpiceMeasurementRuns
from .pspice_output import inspect_output
from .pspice_failure import inspect_failure
from .capture_properties import read_part_properties
from .capture_property_layers import read_property_layers
from .capture_geometry import read_part_geometry
from .capture_objects import query_objects
from .capture_hierarchy import get_hierarchy
from .environment import inspect_environment
from .bridge_rpc import GuiBridgeManager
from .gui_property import GuiPropertyWriter
from .bridge_diagnostics import diagnose


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Evidence(StrictModel):
    level: Literal["documented", "file_present", "runtime_probed", "fixture_passed", "workflow_passed"]
    backend: str
    complete: bool
    coverage: list[str]
    notChecked: list[str]


class Error(StrictModel):
    code: str
    message: str
    phase: str
    retryable: bool
    details: dict[str, Any]
    recoveryAction: str


class Artifact(StrictModel):
    artifactId: str
    kind: str
    workspaceRelativePath: str
    sha256: str
    size: int
    producedByJob: str
    sourceFingerprint: str
    sourceKind: Literal["file_fingerprint", "new_library_spec", "new_design_spec"] | None = None
    createdAt: str
    validationState: Literal["unverified", "validated", "failed", "indeterminate"]


class Envelope(StrictModel):
    schemaVersion: Literal["1.0"]
    requestId: str
    status: Literal["succeeded", "partial", "failed"]
    data: dict[str, Any]
    diagnostics: list[dict[str, Any]]
    artifacts: list[Artifact]
    evidence: Evidence
    error: Error | None


class DesignScope(StrictModel):
    kind: Literal["design"]


class PageScope(StrictModel):
    kind: Literal["page"]
    pageId: str


class PinExpectation(StrictModel):
    schematicName: Annotated[str, Field(min_length=1, max_length=512)]
    pageName: Annotated[str, Field(min_length=1, max_length=512)]
    reference: Annotated[str, Field(min_length=1, max_length=512)]
    pinNumber: Annotated[str, Field(min_length=1, max_length=512)]
    connected: bool
    net: Annotated[str, Field(min_length=1, max_length=512)] | None


class BusBranch(StrictModel):
    index: Annotated[int, Field(ge=0, le=65535)]
    entryPoint: Annotated[list[int], Field(min_length=2, max_length=2)]
    endPoint: Annotated[list[int], Field(min_length=2, max_length=2)]
    wireEnd: Annotated[list[int], Field(min_length=2, max_length=2)]
    expectedBusAttached: bool


class WireAliasLocation(StrictModel):
    aliasId: str
    location: Annotated[list[int], Field(min_length=2, max_length=2)]


class ReferenceChange(StrictModel):
    partId: str
    newReference: Annotated[str, Field(min_length=1, max_length=64)]


class PartHotSpot(StrictModel):
    number: Annotated[str, Field(max_length=512)]
    name: Annotated[str, Field(max_length=512)]
    hotSpot: Annotated[list[int], Field(min_length=2, max_length=2)]


class PlacementPin(StrictModel):
    number: str
    name: str
    hotSpot: Annotated[list[int], Field(min_length=2, max_length=2)]
    connected: bool
    net: str | None


class CacheReplacementInstance(StrictModel):
    partId: str
    libraryPartId: str
    pins: Annotated[list[PlacementPin], Field(min_length=1, max_length=500)]


class MultiunitPlacement(StrictModel):
    libraryPartId: str
    location: Annotated[list[int], Field(min_length=2, max_length=2)]
    rotationCode: Annotated[int, Field(ge=0, le=3)] = 0
    mirrorCode: Annotated[int, Field(ge=0, le=1)] = 0
    expectedPins: Annotated[list[PlacementPin], Field(min_length=1, max_length=500)]


class ExistingUnitPin(StrictModel):
    pinId: str
    connected: bool
    net: Annotated[str, Field(min_length=1, max_length=512)] | None


Scope = Annotated[DesignScope | PageScope, Field(discriminator="kind")]
ToolResult = Annotated[CallToolResult, Envelope]


def packed(row: dict) -> CallToolResult:
    Envelope.model_validate(row)
    return CallToolResult(content=[TextContent(type="text", text=json.dumps(row, ensure_ascii=False))],
                          structured_content=row, is_error=row["status"] == "failed")


class LibraryPinStyleChange(StrictModel):
    long: Annotated[bool, Field(strict=True)] | None = None
    clock: Annotated[bool, Field(strict=True)] | None = None
    dot: Annotated[bool, Field(strict=True)] | None = None


class LibrarySymbolPin(StrictModel):
    position: Annotated[int, Field(ge=0, le=4095)]
    name: Annotated[str, Field(min_length=1, max_length=128)]
    pinType: Annotated[int, Field(ge=0, le=7)]
    start: Annotated[list[int], Field(min_length=2, max_length=2)]
    hotSpot: Annotated[list[int], Field(min_length=2, max_length=2)]
    visible: bool = True


class LibrarySymbolLine(StrictModel):
    start: Annotated[list[int], Field(min_length=2, max_length=2)]
    end: Annotated[list[int], Field(min_length=2, max_length=2)]
    style: Annotated[int, Field(ge=0, le=4)] = 0
    width: Annotated[int, Field(ge=0, le=2)] = 0


class LibrarySymbolDefinition(StrictModel):
    cellName: Annotated[str, Field(min_length=1, max_length=64)]
    partName: Annotated[str, Field(min_length=1, max_length=64)]
    pins: Annotated[list[LibrarySymbolPin], Field(min_length=1, max_length=256)]
    lines: Annotated[list[LibrarySymbolLine], Field(max_length=256)] = Field(default_factory=list)
    vectors: Annotated[list[LibraryCreationVector], Field(max_length=256)] = Field(default_factory=list)


class LibraryPackageChanges(StrictModel):
    referenceTemplate: Annotated[str, Field(min_length=1, max_length=9)] | None = None
    footprint: Annotated[str, Field(max_length=256)] | None = None
    pcbLibrary: Annotated[str, Field(max_length=256)] | None = None

class LibraryPackageUserChange(StrictModel):
    name: Annotated[str, Field(min_length=1, max_length=128)]
    operation: Literal["set", "delete"]
    value: Annotated[str, Field(max_length=4096)] | None = None

class LibraryPhysicalMapping(StrictModel):
    position: Annotated[int, Field(ge=0, le=4095)]
    number: Annotated[str, Field(min_length=1, max_length=32)]
    shared: bool = False
    swapId: Annotated[int, Field(ge=-1, le=126)] = 0


class LibraryDeviceDefinition(StrictModel):
    designator: Annotated[str, Field(max_length=8)]
    position: Annotated[int, Field(ge=0, le=15)]
    cellName: Annotated[str, Field(min_length=1, max_length=64)]
    mapping: Annotated[list[LibraryPhysicalMapping], Field(min_length=1, max_length=256)]


class LibraryCreationSpec(StrictModel):
    packageName: Annotated[str, Field(min_length=1, max_length=64)]
    referenceTemplate: Annotated[str, Field(min_length=1, max_length=9)]
    footprint: Annotated[str, Field(max_length=256)] = ""
    expectedHomogeneous: bool
    symbols: Annotated[list[LibrarySymbolDefinition], Field(min_length=1, max_length=16)]
    devices: Annotated[list[LibraryDeviceDefinition], Field(min_length=1, max_length=16)]


class LibraryFamilySpec(StrictModel):
    packages: Annotated[list[LibraryCreationSpec], Field(min_length=2, max_length=8)]


class NativeMeasurementExpectation(StrictModel):
    name: Annotated[str, Field(min_length=1,max_length=64)]
    field: Literal['value','at','from','to']
    expected: float
    absoluteTolerance: Annotated[float, Field(gt=0,le=1000000)]
    relativeTolerance: Annotated[float, Field(ge=0,le=1)] = 0.0


class SimulationSampleExpectation(StrictModel):
    block: Annotated[int, Field(ge=0, le=127)] = 0
    row: Annotated[int, Field(ge=0, le=99999)]
    traceName: Annotated[str, Field(min_length=1, max_length=512)]
    real: Annotated[float, Field(allow_inf_nan=False)]
    imaginary: Annotated[float, Field(allow_inf_nan=False)] | None = None
    absoluteTolerance: Annotated[float, Field(gt=0, le=1000000, allow_inf_nan=False)]
    relativeTolerance: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)] = 0.0


def create_server(config: Config, *, profile: str = 'development') -> MCPServer:
    if profile not in ('development','validated'):raise ValueError('Unknown server profile')
    from .validated_profile import TOOLS as VALIDATED_TOOLS,protect,narrow_schema,capabilities as validated_capabilities
    capture = CaptureService(config)
    property_edits = CapturePropertyEdits(config, capture)
    user_properties = CaptureUserProperties(config, capture)
    display_properties = CaptureDisplayProperties(config, capture)
    display_fonts = CaptureDisplayFonts(config, capture)
    wire_adds = CaptureWireAdds(config, capture)
    wire_edits = CaptureWireEdits(config, capture)
    graphic_lines = CaptureGraphicLines(config, capture)
    graphic_texts = CaptureGraphicTexts(config, capture)
    part_edits = CapturePartEdits(config, capture)
    reference_edits = CaptureReferenceEdits(config, capture)
    hierarchy_edits = CaptureHierarchyEdits(config, capture)
    nc_edits = CaptureNcEdits(config, capture)
    alias_edits = CaptureAliasEdits(config, capture)
    net_symbol_edits = CaptureNetSymbolEdits(config, capture)
    design_creates = CaptureDesignCreates(config, capture)
    library = LibraryService(config)
    cache_replacements = CaptureCacheReplacements(config, capture, library)
    net_symbol_creates = CaptureNetSymbolCreates(config, capture, library)
    library_creates = LibraryCreates(config, library)
    library_pin_edits = LibraryPinEdits(config, library)
    library_vector_edits = LibraryVectorEdits(config, library)
    library_package_edits = LibraryPackageEdits(config, library)
    placements = CapturePlacements(config, capture, library)
    multiunit_placements = CaptureMultiunitPlacements(config, capture, library)
    simulation_inputs = PSpiceInputs(config)
    input_checks = PSpiceInputChecks(config, simulation_inputs)
    simulation_data = PSpiceDat(config)
    simulation_runs = PSpiceRuns(config, simulation_inputs, simulation_data)
    cli_runs = PSpiceCliRuns(config, simulation_inputs, simulation_data)
    simulation_exports = PSpiceExports(config, simulation_data)
    measurement_runs = PSpiceMeasurementRuns(config, simulation_inputs, simulation_data)
    gui = GuiBridgeManager((config.gui_bridge_config,) if config.gui_bridge_config else (), config.gui_bridge_roots)
    property_writer = GuiPropertyWriter(gui, config)
    wire_adds.editor_host = EditorWireHost(config, gui)
    wire_edits.editor_host = wire_adds.editor_host
    bus_creates = CaptureBusCreates(config, capture, gui)
    native_netlists = CapturePSpiceNetlists(config, capture, gui)
    profile_circuits = PSpiceProfileCircuits(config, native_netlists, simulation_inputs)
    tools = []

    def register(*, readonly: bool):
        def decorator(fn):
            if profile=='validated':
                if fn.__name__ not in VALIDATED_TOOLS:return fn
                fn=protect(fn,{'wire_add':wire_adds,'wire_edit':wire_edits},packed)
            tool = Tool.from_function(fn, annotations=ToolAnnotations(
                read_only_hint=readonly, destructive_hint=False, open_world_hint=False))
            # SDK generates one Pydantic input model per function. Make unknown
            # top-level fields fail as well as the nested strict scope models.
            if profile=='validated':narrow_schema(tool)
            tool.fn_metadata.arg_model.model_config = ConfigDict(extra="forbid", strict=True)
            tool.fn_metadata.arg_model.model_rebuild(force=True)
            tool.parameters = tool.fn_metadata.arg_model.model_json_schema()
            tools.append(tool)
            return fn
        return decorator

    work_pool=ThreadPoolExecutor(max_workers=2,thread_name_prefix="cadence-work")
    diagnostic_pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix="cadence-diagnose")

    @asynccontextmanager
    async def lifespan(app):
        try:yield {}
        finally:
            # Do not block the event loop while a bounded native request finishes.
            # Possibly sent writes retain their durable journal on forced process exit.
            work_pool.shutdown(wait=False,cancel_futures=True)
            diagnostic_pool.shutdown(wait=False,cancel_futures=True)

    async def invoke(fn, *args, coverage=(), not_checked=(), level="runtime_probed", backend="python"):
        try:
            context=contextvars.copy_context()
            pool=diagnostic_pool if fn is diagnose or fn in (property_edits.cancel, cache_replacements.cancel, user_properties.cancel, display_properties.cancel, wire_adds.cancel, wire_edits.cancel, graphic_lines.cancel, graphic_texts.cancel, part_edits.cancel, reference_edits.cancel, hierarchy_edits.cancel, nc_edits.cancel, alias_edits.cancel, net_symbol_edits.cancel, net_symbol_creates.cancel, design_creates.cancel, placements.cancel, multiunit_placements.cancel, simulation_runs.cancel, simulation_exports.cancel, cli_runs.cancel, input_checks.cancel, measurement_runs.cancel, native_netlists.cancel, profile_circuits.cancel, bus_creates.cancel, library_creates.cancel, library_pin_edits.cancel, library_vector_edits.cancel, library_package_edits.cancel) else work_pool
            data = await asyncio.get_running_loop().run_in_executor(pool,context.run,fn,*args)
            row = result(data, backend=backend, level=level, coverage=coverage, not_checked=not_checked)
            if isinstance(data, dict) and (data.get("nextCursor") is not None or data.get("nextOffset") is not None):
                row["status"] = "partial"
                row["evidence"]["complete"] = False
            if isinstance(data, dict) and (data.get("geometryComplete") is False or data.get("comparisonComplete") is False):
                row["status"] = "partial"
                row["evidence"]["complete"] = False
            if isinstance(data, dict) and "artifact" in data:
                row["artifacts"] = [data["artifact"]]
            return packed(row)
        except CadenceError as e:
            return packed(failure(e))
        except OSError:
            return packed(failure(CadenceError("io_error", "A local file operation failed.", "io")))

    @register(readonly=True)
    async def cadence_get_environment(probeLevel: Literal["files", "runtime"] = "files") -> ToolResult:
        """Inspect only the host-configured Cadence installation; runtime starts a command-registration probe, not a design session."""
        return await invoke(inspect_environment, config, probeLevel == "runtime",
                            level="runtime_probed" if probeLevel == "runtime" else "file_present",
                            coverage=("configured_installation",), not_checked=("gui", "simulation", "save_reopen"))

    @register(readonly=True)
    async def cadence_get_capabilities() -> ToolResult:
        """Describe implemented experimental features separately from runtime probes and unimplemented workflows."""
        if profile=='validated':return packed(result(validated_capabilities(),level='documented',coverage=('validated_release_registry',),not_checked=('current_runtime','full_project_completion')))
        features = {
            "environment.files": "implemented", "environment.runtime_probe": "implemented",
            "pspice.parameter_step": "experimental_literal_param_list_cli_only",
            "pspice.profile_circuit": "experimental_explicit_or_native_checked_global_library_selection",
            "capture.native_pspice_netlist": "experimental_same_directory_design_single_profile_native_task",
            "capture.single_dsn_copy": "implemented", "capture.design_create": "experimental_ascii_root_and_single_empty_page", "capture.library_create": "experimental_declared_single_or_family_graph_and_basic_vectors", "capture.library_vectors": "experimental_part_bound_native_order", "capture.library_vector_edit": "experimental_inplace_fields_and_delete_modeled_preservation", "capture.library_package_edit": "experimental_fixed_fields_and_explicit_string_properties", "capture.library_pin_edit": "experimental_symbol_geometry_flags_and_device_pad_mapping", "capture.library_pin_style_query": "experimental_native_scalar_pin_flags", "capture.shared_pin_definition_query": "experimental_explicit_shared_enumeration", "capture.definition_query": "experimental", "capture.part_properties": "experimental", "capture.property_layers": "experimental", "capture.display_property_layout": "experimental_unambiguous_definitions", "capture.display_font": "experimental_existing_instance_full_descriptor_and_inheritance", "capture.user_property_lifecycle": "experimental_unambiguous_definitions", "capture.isolated_property_edit": "experimental_unambiguous_definitions", "capture.cache_binding": "experimental_source_qualified_placed_package", "capture.cache_replacement": "experimental_compatible_physical_pins_modeled_instance_preservation", "capture.part_geometry": "experimental", "capture.connection_objects": "experimental", "capture.wire_add": "experimental_explicit_definition_expectations", "capture.wire_edit": "experimental_two_point_scalar", "capture.placement": "experimental_explicit_library_and_hotspots", "capture.alternate_view_placement": "experimental_source_pin_and_basic_vector_identity", "capture.multiunit_placement": "experimental_atomic_complete_package", "capture.unit_pose_delete": "experimental_native_identity_pinid_expectations", "capture.cached_unit_add": "experimental_existing_group_missing_device", "capture.graphic_objects": "experimental", "capture.page_vectors": "experimental_typed_local_definitions_and_native_control_points", "capture.page_dimensions": "experimental_native_sizes_units_flags", "capture.page_graphic_bounds": "experimental_declared_control_points_only", "capture.graphic_line_add": "experimental_rotation_zero", "capture.graphic_text_add": "experimental_definition_anchor_and_modeled_preservation", "capture.graphic_text_edit": "experimental_bound_update_delete_and_modeled_preservation", "capture.part_edit": "experimental_explicit_definition_pose_delete", "capture.reference_map": "experimental_single_unit_definition_map", "capture.package_reference_map": "experimental_explicit_whole_package_definition_map", "capture.net_symbol_edit": "experimental_scalar_name_delete_page_membership", "capture.net_symbol_create": "experimental_source_bound_page_definition", "capture.net_symbols": "experimental_kind_name_metadata", "capture.alias_edit": "experimental_scalar_alias_preserve_page_membership", "capture.nc_edit": "experimental_single_unit_unbound_scalar_pin", "capture.hierarchy_clone": "experimental_top_level_internal_block_reuse", "capture.occurrence_structure": "experimental_revision_scoped_unit_identity", "capture.occurrence_properties": "experimental_component_and_immediate_definition_layers",
            "capture.page_query": "experimental", "capture.pin_net_definition": "experimental", "capture.compare_connections": "experimental_selected_definitions",
            "capture.editor_wire_add": "experimental_24_1_fixed_output_editor", "capture.editor_wire_delete": "experimental_24_1_selection_guarded_delete", "capture.editor_wire_occurrence": "experimental_unique_schematic_reference", "capture.bus_create": "experimental_fixed_vertical_ordinary_bus_editor", "capture.bus_inventory": "experimental_named_members_and_native_entry_links", "capture.snapshot": "experimental", "capture.wire_geometry": "experimental", "capture.occurrence_connectivity": "unavailable",
            "capture.olb": "experimental_read_only", "capture.cache_query": "experimental_read_only", "capture.write_save_reopen": "unavailable",
            "capture.gui_note_write_save_reopen": "experimental_fixture_only", "capture.gui_job_resolution": "experimental_fixture_only", "capture.gui_diagnose": "experimental_config_required",
            "capture.gui_status": "experimental_config_required", "capture.gui_sessions": "experimental_config_required", "capture.gui_drc_pdf": "unavailable", "pspice.prepare": "experimental_explicit_references_only", "pspice.input_check": "experimental_native_parse_setup_only", "pspice.run": "experimental_independent_engine_tcl", "pspice.cli_run": "experimental_official_psp_cmd_r", "pspice.dat": "experimental_analog_and_unflagged_digital_change_records", "pspice.dat_export": "experimental_bound_csv_json_rows", "pspice.native_measurements": "experimental_complete_analysis_named_fields", "pspice.failure_diagnostics": "experimental_stopped_job_explicit_errors", "pspice.inspect_output": "experimental_imported_out_diagnostics_bias_only",
        }
        return packed(result({"features": features, "backend": "standalone", "readOnly": False, "writesRequirePlan": True,
                              "writeTargets": "new_isolated_copies_or_prepared_gui_fixtures", "dependencyClosureVerified": False}, level="documented",
                             coverage=("implementation_registry",), not_checked=("current_runtime",)))

    @register(readonly=True)
    async def capture_gui_status() -> ToolResult:
        """Read live status when exactly one authenticated host-registered GUI instance is available; use explicit attach for multiple instances."""
        if config.gui_bridge_config is None and not config.gui_bridge_roots:
            return packed(failure(CadenceError("bridge_unavailable", "No GUI bridge binding is configured.")))
        return await invoke(gui.status, backend="capture_gui_bridge",
                            coverage=("authenticated_instance_binding", "active_design_path"),
                            not_checked=("gui_mutation", "native_drc", "unsaved_contents"))

    @register(readonly=True)
    async def capture_gui_instances() -> ToolResult:
        """Discover and authenticate instances only within host-registered bridge directories; no arbitrary endpoint input."""
        return await invoke(gui.discover, backend="capture_gui_bridge", coverage=("authenticated_instance_discovery",))

    @register(readonly=False)
    async def capture_gui_attach(instanceId: str, access: Literal["read", "write"] = "read") -> ToolResult:
        """Attach a GUI session to one authenticated instance and generation; default read, experimental write requires an explicitly prepared fixture binding."""
        return await invoke(gui.attach, instanceId, access, backend="capture_gui_bridge", coverage=("gui_session_binding",))

    @register(readonly=True)
    async def capture_gui_query(sessionId: str, entity: Literal["status", "pages", "selection", "drc_configuration", "drc_counts"]) -> ToolResult:
        """Read live Capture state, pages, selection, native DRC configuration or observed counters. Configuration/counters do not certify completed rule execution."""
        return await invoke(gui.query, sessionId, entity, backend="capture_gui_bridge",
                            coverage=("live_gui_read",), not_checked=("write_lease", "native_drc", "connectivity_validation"))

    @register(readonly=False)
    async def capture_gui_detach(sessionId: str) -> ToolResult:
        """Release this logical GUI session without closing or saving the Capture design."""
        return await invoke(gui.detach, sessionId, backend="capture_gui_bridge", coverage=("gui_session_release",))

    @register(readonly=False)
    async def capture_gui_plan_note(sessionId: str, schematicName: str, pageName: str, reference: str,
                                    value: Annotated[str, Field(max_length=512)]) -> ToolResult:
        """Preview one MCP_NOTE metadata change on an explicitly prepared fixture write session; no electrical property editing."""
        return await invoke(property_writer.plan, sessionId, schematicName, pageName, reference, value,
                            backend="capture_gui_bridge", coverage=("fixed_note_plan",))

    @register(readonly=False)
    async def capture_gui_apply_note(planId: str, planDigest: str,
                                     idempotencyKey: Annotated[str, Field(min_length=1, max_length=128)]) -> ToolResult:
        """Apply one immutable fixture note plan, save, reopen in independent workers and compare definition pin nets; ambiguous outcomes are never replayed."""
        return await invoke(property_writer.apply, planId, planDigest, idempotencyKey,
                            backend="capture_gui_bridge", coverage=("note_write_save_reopen", "definition_pin_net_comparison"),
                            not_checked=("occurrence_connectivity", "native_drc"))

    @register(readonly=True)
    async def capture_gui_jobs() -> ToolResult:
        """List bounded durable note jobs in host-registered private bindings, including after server restart; never replay writes."""
        return await invoke(property_writer.jobs, coverage=("durable_job_status",))

    @register(readonly=False)
    async def capture_gui_cancel_note(planId: str, planDigest: str) -> ToolResult:
        """Cancel a pending note plan; started writes cannot be cancelled or rolled back."""
        return await invoke(property_writer.cancel, planId, planDigest, coverage=("pending_plan_cancel",))

    @register(readonly=False)
    async def capture_gui_recover_note(planId: str, planDigest: str) -> ToolResult:
        """Reconcile a started note job without replay: verify a saved result, or retire a still-pending native plan with unchanged file bytes. Lost native context requires manual recovery."""
        return await invoke(property_writer.recover, planId, planDigest, backend="capture_gui_bridge",
                            coverage=("native_outcome_reconciliation", "no_mutation_replay"),
                            not_checked=("occurrence_connectivity", "native_drc"))

    @register(readonly=True)
    async def capture_gui_diagnose() -> ToolResult:
        """Classify registered bridge/process/design/window/lock failures with recovery actions; read-only and never waits for the GUI operation lock."""
        return await invoke(diagnose, gui, coverage=("bridge_diagnosis",), not_checked=("automatic_repair",))

    @register(readonly=False)
    async def capture_gui_review_note(planId: str, planDigest: str) -> ToolResult:
        """Produce an independent forensic review of a crashed note job; keeps the lock and requires proof the old Capture process has stopped."""
        return await invoke(property_writer.review, planId, planDigest, backend="capture_dbo",
                            coverage=("forensic_file_review",), not_checked=("native_completion", "lock_release"))

    @register(readonly=False)
    async def capture_gui_resolve_note(planId: str, planDigest: str, reviewId: str, reviewDigest: str,
                                       decision: Literal["accept_saved_artifact", "close_unchanged"]) -> ToolResult:
        """Explicitly close a crashed job using a fresh review digest; release only its own lock, never edit/replay a design or claim a missing native receipt."""
        return await invoke(property_writer.resolve, planId, planDigest, reviewId, reviewDigest, decision,
                            coverage=("explicit_forensic_resolution",), not_checked=("native_completion",))

    @register(readonly=False)
    async def pspice_plan_input_check(simulationId: str,timeoutSeconds: Annotated[int,Field(ge=1,le=600)] | None = None) -> ToolResult:
        """Bind a prepared immutable CIR closure for fixed native parser/setup validation. Does not run analyses or certify numerical results. Explicit includes only; no implicit model-lookup closure certification."""
        return await invoke(input_checks.plan,simulationId,timeoutSeconds,backend='pspice_native_setup',coverage=('frozen_input_check_plan',),not_checked=('analysis_execution','numerical_results'))

    @register(readonly=False)
    async def pspice_apply_input_check(planId: str,planDigest: str,idempotencyKey: Annotated[str,Field(min_length=1,max_length=128)]) -> ToolResult:
        """Run fixed PSpiceSetupAnalysis/FINISH/cleanup once in an owned process, reject native OUT errors, verify exact rebased inputs and receipt. Setup success is not solver success."""
        return await invoke(input_checks.apply,planId,planDigest,idempotencyKey,backend='pspice_native_setup',coverage=('native_parser_setup','input_artifact_identity'),not_checked=('numerical_results','convergence','electrical_design_safety'))

    @register(readonly=True)
    async def pspice_input_check_jobs(offset: Annotated[int,Field(ge=0,le=4096)]=0,limit: Annotated[int,Field(ge=1,le=100)]=50) -> ToolResult:
        """Page durable native input-check jobs without execution."""
        return await invoke(input_checks.jobs,offset,limit,coverage=('durable_input_check_jobs',))

    @register(readonly=False)
    async def pspice_cancel_input_check(planId: str,planDigest: str) -> ToolResult:
        """Cancel a pending input check or this server's active owned worker."""
        return await invoke(input_checks.cancel,planId,planDigest,coverage=('owned_input_check_cancel',))

    @register(readonly=False)
    async def pspice_recover_input_check(planId: str,planDigest: str) -> ToolResult:
        """Verify stopped existing input-check artifacts without rerun. A missing native setup receipt cannot be certified from absence of OUT errors."""
        return await invoke(input_checks.recover,planId,planDigest,backend='pspice_native_setup',coverage=('existing_input_check_verification',),not_checked=('native_completion','numerical_results'))

    @register(readonly=True)
    async def pspice_inspect_input_check(planId: str,planDigest: str) -> ToolResult:
        """Read a successful native setup report after every bound file hash passes. analysisExecuted and solverSuccessVerified remain false."""
        return await invoke(input_checks.inspect,planId,planDigest,backend='pspice_native_setup',coverage=('verified_input_check_report',),not_checked=('numerical_results',))

    @register(readonly=False)
    async def pspice_plan_profile_circuit(netlistPlanId: str, netlistPlanDigest: str,
            libraryPaths: Annotated[list[str], Field(max_length=16)], includeAliases: bool,
            expectedDirectives: Annotated[list[str], Field(min_length=1, max_length=16)],
            inputBudget: Literal["standard", "extended"] = "standard", configurationIni: str | None = None) -> ToolResult:
        """Freeze a verified NET/ALS task, its profile and allowed model closure. Choose explicit libraryPaths or configurationIni with an empty libraryPaths list. INI mode preserves the original bytes and checks native merged global library selection in one search directory; profile/local/include/stimulus overlays are refused. Declare expected analysis/probe/option lines independently. No global configuration writes or encrypted-model execution exemption."""
        return await invoke(profile_circuits.plan, netlistPlanId, netlistPlanDigest, libraryPaths, includeAliases, expectedDirectives, inputBudget, configurationIni,
                            backend="pspice_profile", coverage=("bound_netlist_profile_plan", "explicit_library_closure"), not_checked=("inherited_nominal_configuration", "complete_profile_semantics", "solver"))

    @register(readonly=False)
    async def pspice_apply_profile_circuit(planId: str, planDigest: str,
            idempotencyKey: Annotated[str, Field(min_length=1, max_length=128)]) -> ToolResult:
        """Generate a new CIR once with the fixed native CorSimSrvr Tcl script and private INI. Verify native process/receipt, declared directives, exact NET/ALS/library references and unchanged staged inputs. No solver run."""
        return await invoke(profile_circuits.apply, planId, planDigest, idempotencyKey, backend="pspice_profile",
                            coverage=("native_profile_circuit_generation", "explicit_configuration_verification", "declared_directives"), not_checked=("inherited_nominal_configuration", "complete_profile_semantics", "solver", "numerical_results"))

    @register(readonly=True)
    async def pspice_profile_circuit_jobs(offset: Annotated[int, Field(ge=0, le=4096)] = 0,
                                           limit: Annotated[int, Field(ge=1, le=100)] = 50) -> ToolResult:
        """Page persisted profile-to-CIR jobs without starting native work."""
        return await invoke(profile_circuits.jobs, offset, limit, coverage=("durable_profile_circuit_jobs",))

    @register(readonly=False)
    async def pspice_cancel_profile_circuit(planId: str, planDigest: str) -> ToolResult:
        """Cancel a pending plan or this server's owned profile worker. Partial CIR artifacts remain unverified; Capture is never terminated."""
        return await invoke(profile_circuits.cancel, planId, planDigest, coverage=("owned_profile_worker_cancel",))

    @register(readonly=False)
    async def pspice_recover_profile_circuit(planId: str, planDigest: str) -> ToolResult:
        """Verify existing profile task output after proof the original worker stopped; never regenerate the circuit."""
        return await invoke(profile_circuits.recover, planId, planDigest, backend="pspice_profile",
                            coverage=("existing_profile_circuit_verification", "no_mutation_replay"), not_checked=("solver", "numerical_results"))

    @register(readonly=False)
    async def pspice_prepare_profile_circuit(planId: str, planDigest: str) -> ToolResult:
        """Prepare the CIR of a verified profile task for existing CLI tools. Read only that owned task's validated artifact closure, not arbitrary workspace paths. Does not regenerate CIR or run a solver."""
        return await invoke(profile_circuits.open_input, planId, planDigest, backend="pspice_profile",
                            coverage=("verified_profile_artifact_input", "explicit_reference_closure"), not_checked=("model_validity", "solver", "numerical_results"))

    @register(readonly=False)
    async def pspice_plan_cli_run(simulationId: str,analysis: Literal['dc','ac','transient'],expectedSamples: list[SimulationSampleExpectation] | None = None,timeoutSeconds: Annotated[int,Field(ge=1,le=600)] | None = None) -> ToolResult:
        """Plan official noninteractive psp_cmd /r on an immutable prepared CIR closure. Supports one bounded, single-line .STEP PARAM name LIST of literal values; other STEP forms refuse. Parameter sweeps require this CLI backend, since the single-analysis engine does not iterate them. Fixed executable/flags and owned output only. Use backend=cli when opening DAT or inspecting OUT."""
        return await invoke(cli_runs.plan,simulationId,analysis,None if expectedSamples is None else [p.model_dump() for p in expectedSamples],timeoutSeconds,backend='pspice_cli',coverage=('durable_cli_plan','frozen_closure'),not_checked=('implicit_model_lookup_closure','full_spice_syntax'))

    @register(readonly=False)
    async def pspice_apply_cli_run(planId: str,planDigest: str,idempotencyKey: Annotated[str,Field(min_length=1,max_length=128)]) -> ToolResult:
        """Run official psp_cmd /r once, wait for owned process exit, retain raw output identity, independently read DAT and verify declared samples. Exit0 alone cannot certify success."""
        return await invoke(cli_runs.apply,planId,planDigest,idempotencyKey,backend='pspice_cli',coverage=('official_cli_run','native_output_identity','declared_sample_verification'),not_checked=('unrequested_waveform_values','electrical_design_safety'))

    @register(readonly=True)
    async def pspice_cli_run_jobs(offset: Annotated[int,Field(ge=0,le=4096)]=0,limit: Annotated[int,Field(ge=1,le=100)]=50) -> ToolResult:
        """Page durable official CLI jobs without execution."""
        return await invoke(cli_runs.jobs,offset,limit,coverage=('durable_cli_jobs',))

    @register(readonly=False)
    async def pspice_cancel_cli_run(planId: str,planDigest: str) -> ToolResult:
        """Cancel a pending or this server's active owned CLI process tree."""
        return await invoke(cli_runs.cancel,planId,planDigest,coverage=('owned_cli_cancel',))

    @register(readonly=False)
    async def pspice_recover_cli_run(planId: str,planDigest: str) -> ToolResult:
        """Verify existing stopped CLI artifacts, raw/canonical hashes and declared numerical samples without rerun. Missing completion receipt keeps nativeCompletionVerified false."""
        return await invoke(cli_runs.recover,planId,planDigest,backend='pspice_cli',coverage=('existing_cli_artifact_verification',),not_checked=('native_completion',))

    @register(readonly=False)
    async def pspice_plan_run(simulationId: str, analysis: Literal["dc", "ac", "transient"],
                              expectedSamples: list[SimulationSampleExpectation] | None = None,
                              timeoutSeconds: Annotated[int, Field(ge=1, le=600)] | None = None) -> ToolResult:
        """Plan one fixed independent PSpice engine analysis over a prepared immutable CIR closure. Output is a new owned task; no CLI invocation. Optional bounded independent trace-row expectations certify only those declared values. Unsupported file/control directives are refused; implicit model lookup and full SPICE syntax are not certified."""
        return await invoke(simulation_runs.plan, simulationId, analysis,
                            None if expectedSamples is None else [r.model_dump() for r in expectedSamples], timeoutSeconds,
                            backend="pspice_engine_tcl", coverage=("durable_simulation_plan", "prepared_closure_binding"),
                            not_checked=("cli_backend", "implicit_model_lookup_closure", "full_spice_syntax"))

    @register(readonly=False)
    async def pspice_apply_run(planId: str, planDigest: str,
                                idempotencyKey: Annotated[str, Field(min_length=1, max_length=128)]) -> ToolResult:
        """Run once in an owned process tree, finish/close outputs, independently read DAT and verify declared samples. Never replay a started or failed run."""
        return await invoke(simulation_runs.apply, planId, planDigest, idempotencyKey, backend="pspice_engine_tcl",
                            coverage=("owned_engine_run", "fresh_out_dat_manifest", "declared_sample_verification"), not_checked=("electrical_design_safety", "unrequested_waveform_values"))

    @register(readonly=True)
    async def pspice_run_jobs(offset: Annotated[int, Field(ge=0, le=4096)] = 0,
                              limit: Annotated[int, Field(ge=1, le=100)] = 50) -> ToolResult:
        """Page durable simulation jobs and terminal errors; no engine launch."""
        return await invoke(simulation_runs.jobs, offset, limit, coverage=("durable_simulation_jobs",))

    @register(readonly=False)
    async def pspice_cancel_run(planId: str, planDigest: str) -> ToolResult:
        """Cancel a pending run or this server's active owned process tree; retain uncertain artifacts."""
        return await invoke(simulation_runs.cancel, planId, planDigest, coverage=("owned_engine_cancel",))

    @register(readonly=False)
    async def pspice_recover_run(planId: str, planDigest: str) -> ToolResult:
        """Verify existing stopped run inputs/OUT/DAT and declared samples; never rerun. Missing native receipt keeps nativeCompletionVerified false."""
        return await invoke(simulation_runs.recover, planId, planDigest, backend="pspice_engine_tcl",
                            coverage=("existing_simulation_artifact_verification",), not_checked=("native_completion",))

    @register(readonly=False)
    async def pspice_open_run_dat(planId: str, planDigest: str, backend: Literal['engine','cli']='engine') -> ToolResult:
        """Open a verified run DAT as an immutable public query snapshot after all job artifact hashes pass. Does not expand public read roots."""
        return await invoke((simulation_runs if backend=='engine' else cli_runs).open_dat, planId, planDigest, backend="pspice_data",
                            coverage=("verified_run_dat_snapshot", "plan_artifact_association"))

    @register(readonly=True)
    async def pspice_inspect_run_output(planId: str, planDigest: str, backend: Literal['engine','cli']='engine') -> ToolResult:
        """Inspect immutable OUT diagnostics from a verified run; native MEASURE values are not parsed."""
        return await invoke((simulation_runs if backend=='engine' else cli_runs).inspect_output, planId, planDigest, backend="pspice_engine",
                            coverage=("verified_run_out", "job_artifact_binding", "diagnostics_bias"),
                            not_checked=("native_measurements", "full_diagnostic_grammar", "design_safety"))

    @register(readonly=True)
    async def pspice_inspect_run_failure(planId: str,planDigest: str,kind: Literal['engine','measurement','input_check','cli']='engine') -> ToolResult:
        """Read bounded OUT/receipt diagnostics from a stopped failed/cancelled owned run. Binds observation hashes to the task, checks available input closure, never promotes failed outputs or reruns. Explicit diagnostics classify failures; timeout alone does not establish a license fault."""
        return await invoke(inspect_failure,{'engine':simulation_runs,'measurement':measurement_runs,'input_check':input_checks,'cli':cli_runs}[kind],planId,planDigest,
                            backend='pspice_failed_job_observation',coverage=('stopped_failed_job_diagnostics','observed_artifact_hashes'),not_checked=('solver_success','complete_error_grammar','license_server_health'))

    @register(readonly=False)
    async def pspice_plan_measure_run(simulationId: str, analysis: Literal['dc','ac','transient'],
                                      expectedMeasurements: list[NativeMeasurementExpectation],
                                      timeoutSeconds: Annotated[int,Field(ge=1,le=600)] | None = None) -> ToolResult:
        """Plan complete native analysis of one prepared analysis with .MEASURE declarations and independent named value/at/from/to expectations. Native measurements are distinct from sampled DAT statistics; WHEN time is the at field. Fixed PSpiceDoAnalysis entry, new owned output only."""
        return await invoke(measurement_runs.plan, simulationId, analysis,[r.model_dump() for r in expectedMeasurements],timeoutSeconds,
                            backend='pspice_complete_analysis',coverage=('native_measurement_plan','frozen_declarations_and_expectations'),not_checked=('cli_backend','full_measurement_grammar','electrical_design_safety'))

    @register(readonly=False)
    async def pspice_apply_measure_run(planId: str,planDigest: str,idempotencyKey: Annotated[str,Field(min_length=1,max_length=128)]) -> ToolResult:
        """Run complete native analysis once; verify fresh DAT, complete OUT and every declared measurement result name. Evaluation Failed or mismatched expected fields refuse acceptance."""
        return await invoke(measurement_runs.apply,planId,planDigest,idempotencyKey,backend='pspice_complete_analysis',coverage=('native_measurement_fields','owned_process_tree','artifact_identity'))

    @register(readonly=True)
    async def pspice_measure_run_jobs(offset: Annotated[int,Field(ge=0,le=4096)]=0,limit: Annotated[int,Field(ge=1,le=100)]=50) -> ToolResult:
        """Page durable native measurement jobs without execution."""
        return await invoke(measurement_runs.jobs,offset,limit,coverage=('durable_measurement_jobs',))

    @register(readonly=False)
    async def pspice_cancel_measure_run(planId: str,planDigest: str) -> ToolResult:
        """Cancel a pending native measurement run or its active owned process tree."""
        return await invoke(measurement_runs.cancel,planId,planDigest,coverage=('owned_measurement_cancel',))

    @register(readonly=False)
    async def pspice_recover_measure_run(planId: str,planDigest: str) -> ToolResult:
        """Verify stopped existing native measurement outputs without rerunning; missing receipt keeps nativeCompletionVerified false."""
        return await invoke(measurement_runs.recover,planId,planDigest,backend='pspice_complete_analysis',coverage=('existing_native_measurement_verification',),not_checked=('native_completion',))

    @register(readonly=True)
    async def pspice_inspect_run_measurements(planId: str,planDigest: str) -> ToolResult:
        """Read verified native .MEASURE fields/checks plus conservative field-unit annotations after bound artifact hashes pass. Units derive from simple verified V/I expressions and declared analysis/source sweep; unknown dimensions remain null. Native text contains no native unit metadata; raw numeric evidence and whole-design acceptance remain unchanged."""
        return await invoke(measurement_runs.inspect_measurements,planId,planDigest,backend='pspice_complete_analysis',coverage=('verified_native_measurements','job_artifact_binding','conservative_field_unit_annotations'),not_checked=('native_unit_metadata','unsupported_expression_dimensions','design_safety'))

    @register(readonly=False)
    async def pspice_plan_dat_export(datId: str, block: Annotated[int, Field(strict=True, ge=0, le=127)],
                                    traceName: str, format: Literal["csv", "json"] = "csv",
                                    offset: Annotated[int, Field(strict=True, ge=0, le=100000)] = 0,
                                    count: Annotated[int, Field(strict=True, ge=1, le=100000)] | None = None) -> ToolResult:
        """Freeze one bound analog trace/range and axis for CSV/JSON export. Includes analog partitions of verified mixed metadata; digital values refuse. Fixed numeric CSV columns, separate unit/provenance manifest, new owned output only. Source run acceptance is preserved as provenance, not a new oracle for exported rows."""
        return await invoke(simulation_exports.plan, datId, block, traceName, format, offset, count,
                            backend="pspice_data", coverage=("bound_numeric_export_plan",),
                            not_checked=("digital_logic_samples", "native_units", "new_numerical_oracle"))

    @register(readonly=False)
    async def pspice_apply_dat_export(planId: str, planDigest: str,
                                     idempotencyKey: Annotated[str, Field(min_length=1, max_length=128)]) -> ToolResult:
        """Serialize a frozen DAT range in an owned worker, then independently reopen the copied DAT and verify every exported sample/axis value. Return a hashed data/units/provenance manifest. Started writes never replay."""
        return await invoke(simulation_exports.apply, planId, planDigest, idempotencyKey,
                            backend="pspice_data_export", coverage=("owned_numeric_export", "native_reopen_sample_identity"),
                            not_checked=("new_numerical_oracle", "native_units", "digital_logic_samples"))

    @register(readonly=True)
    async def pspice_dat_export_jobs(offset: Annotated[int, Field(ge=0, le=4096)] = 0,
                                     limit: Annotated[int, Field(ge=1, le=100)] = 50) -> ToolResult:
        """Page durable numeric export jobs without reading or writing samples."""
        return await invoke(simulation_exports.jobs, offset, limit, coverage=("durable_export_jobs",))

    @register(readonly=False)
    async def pspice_cancel_dat_export(planId: str, planDigest: str) -> ToolResult:
        """Cancel a pending export or this server's active owned serializer; retain incomplete artifacts."""
        return await invoke(simulation_exports.cancel, planId, planDigest, coverage=("owned_export_cancel",))

    @register(readonly=False)
    async def pspice_recover_dat_export(planId: str, planDigest: str) -> ToolResult:
        """Verify existing stopped export bytes against its frozen declaration and a fresh native DAT read; never regenerate numeric output. A missing validation manifest may be created after verification. Missing receipt keeps workerCompletionVerified false."""
        return await invoke(simulation_exports.recover, planId, planDigest,
                            backend="pspice_data_export", coverage=("existing_export_verification",),
                            not_checked=("worker_completion", "new_numerical_oracle"))

    @register(readonly=False)
    async def pspice_dat_open(sourceDat: str) -> ToolResult:
        """Import an allowed DAT file and read native analog/digital/mixed block and trace metadata on an isolated immutable copy. Digital aliases/counts are checked separately. Analog samples from completely described mixed blocks are supported; unflagged digital change records use the dedicated digital endpoint; native flagged states remain unsupported. No simulation or solver-success claim."""
        return await invoke(simulation_data.open, sourceDat, backend="pspice_data",
                            coverage=("imported_dat_metadata",), not_checked=("fresh_solver_run", "numerical_oracle", "digital_samples"))

    @register(readonly=True)
    async def pspice_dat_query(datId: str, entity: Literal["block", "trace"], block: int | None = None,
                                offset: int = 0, limit: int = 100) -> ToolResult:
        """Page imported DAT blocks or exact canonical trace names with aliases. Units report name conventions or unknown, never an undocumented native unit declaration."""
        return await invoke(simulation_data.query, datId, entity, block, offset, limit, backend="pspice_data",
                            coverage=("dat_metadata_pagination",), not_checked=("job_association", "native_units"))

    @register(readonly=True)
    async def pspice_dat_samples(datId: str, block: int, traceName: str, offset: int = 0, limit: int = 1000) -> ToolResult:
        """Read finite analog real/imaginary samples of one exact trace or alias, including the analog partition of a completely described mixed block. Digital traces are rejected before invoking the numeric reader. Bounded paging and snapshot hash checks apply. Native CSV decode is bounded to 100000 rows per trace, including when requesting a small page."""
        return await invoke(simulation_data.samples, datId, block, traceName, offset, limit, backend="pspice_data",
                            coverage=("dat_analog_samples", "real_complex_values", "sample_pagination"),
                            not_checked=("fresh_solver_run", "job_association", "numerical_oracle", "native_units", "digital_samples"))

    @register(readonly=True)
    async def pspice_dat_digital_samples(datId: str, block: Annotated[int, Field(strict=True, ge=0, le=127)], traceName: str,
                                       offset: Annotated[int, Field(strict=True, ge=0)] = 0,
                                       limit: Annotated[int, Field(strict=True, ge=1, le=1000)] = 1000) -> ToolResult:
        """Read unflagged native digital transient change records with time, six enum states and strength codes. Resolve exact catalog aliases before invoking getDigital; axes/missing names never reach it. Pagination uses per-trace records, not block header rows. Unknown native state flags reject the full trace; opaque tail words are retained privately and never returned. No voltage, resistance, hazard or fresh solver-success claim."""
        return await invoke(simulation_data.digital_samples, datId, block, traceName, offset, limit, backend="pspice_data",
                            coverage=("unflagged_digital_change_records", "digital_catalog_binding", "record_pagination"),
                            not_checked=("native_flagged_state_semantics", "strength_resistance_mapping", "opaque_tail_semantics", "fresh_solver_run"))

    @register(readonly=True)
    async def pspice_dat_measure(datId: str, block: Annotated[int, Field(strict=True, ge=0, le=127)], traceName: str,
                                  measurement: Literal["summary", "value_at", "first_crossing"] = "summary",
                                  component: Literal["real", "imaginary", "magnitude"] = "real",
                                  atAxis: Annotated[float, Field(strict=True, allow_inf_nan=False)] | None = None,
                                  threshold: Annotated[float, Field(strict=True, allow_inf_nan=False)] | None = None,
                                  direction: Literal["either", "rising", "falling"] = "either") -> ToolResult:
        """Measure finite analog DAT samples. Summary distinguishes sample mean/RMS from axis-weighted piecewise-linear interval mean/RMS and signed trapezoidal area in stored axis order. value_at and first_crossing use piecewise-linear selected-component interpolation in increasing axis; no extrapolation, duplicate axes or discontinuity inference. First crossing may report not-found or plateau. Preserve imported/verified-job provenance; never infer circuit safety or native .MEAS success."""
        return await invoke(simulation_data.measure, datId, block, traceName, measurement, component, atAxis, threshold, direction,
                            backend="pspice_data", coverage=("sampled_waveform_measurement", "finite_monotonic_axis", "provenance_preservation"),
                            not_checked=("between_sample_behavior", "native_measure_directives", "electrical_design_safety"))

    @register(readonly=False)
    async def pspice_dat_close(datId: str) -> ToolResult:
        """Release imported DAT registration. Every native read already closes its own file/process; retain copied input and evidence."""
        return await invoke(simulation_data.close, datId, coverage=("dat_session_release",))

    @register(readonly=True)
    async def pspice_inspect_output(sourceOutput: str,
                                    encoding: Literal["utf-8-sig", "cp1252", "cp936"] = "utf-8-sig") -> ToolResult:
        """Read an imported OUT file from configured roots, preserve bytes, and extract coded diagnostics and bias voltage tables. Completion markers cannot prove solver success or association with a current job. Not a waveform/measurement reader."""
        return await invoke(inspect_output, config, sourceOutput, encoding,
                            coverage=("imported_out_diagnostics", "bias_voltage_tables"),
                            not_checked=("fresh_solver_run", "job_association", "measurements", "waveforms", "full_diagnostic_grammar"))

    @register(readonly=True)
    async def pspice_inspect_library(sourceLibrary: str, pinCount: Annotated[int, Field(ge=0, le=4096)] = 0,
                                    offset: Annotated[int, Field(ge=0, le=100000)] = 0,
                                    limit: Annotated[int, Field(ge=1, le=1000)] = 100) -> ToolResult:
        """Inspect top-level native model/subcircuit names, AKO references and formal ports from one copied .lib; count local definitions without returning their metadata. Pin count marks matching subcircuits; it does not filter out other rows. Referenced libraries are refused; no engine execution, model-validity or dependency-closure claim."""
        return await invoke(inspect_library_metadata, config, sourceLibrary, pinCount, offset, limit,
                            backend="native_pspice_library_parser", coverage=("library_definition_metadata", "source_snapshot_identity"),
                            not_checked=("dependency_closure", "model_validity", "solver", "physical_pin_mapping"))

    @register(readonly=False)
    async def pspice_prepare(sourceCircuit: str, inputEncoding: Literal["utf-8", "preserve-bytes"] = "utf-8", inputBudget: Literal["standard", "extended"] = "standard") -> ToolResult:
        """Prepare a new copied CIR input with bounded explicit .INC/.INCLUDE/.LIB references from configured roots. Standard budget64files/32MiB; explicit extended256files/64MiB, both8MiB/file/depth32. Default strict UTF-8; explicit preserve-bytes retains opaque model bytes without guessing/transcoding, but reference filenames must be valid UTF-8. Preserve originals and rewrite copied references. No engine run or full syntax/model/implicit-file validation."""
        return await invoke(simulation_inputs.prepare, sourceCircuit, inputEncoding, inputBudget, backend="python",
                            coverage=("explicit_simulation_reference_snapshot",),
                            not_checked=("engine_syntax", "model_validity", "implicit_or_embedded_file_references", "simulation"))

    @register(readonly=True)
    async def pspice_get_input(simulationId: str) -> ToolResult:
        """Verify hashes of a registered prepared CIR/model snapshot and its preserved originals; this is not a solver result."""
        return await invoke(simulation_inputs.get, simulationId, coverage=("prepared_input_fingerprints",),
                            not_checked=("engine_syntax", "model_validity", "simulation"))

    @register(readonly=False)
    async def pspice_close_input(simulationId: str) -> ToolResult:
        """Release the server's prepared-input registration; retain all copied evidence files and never touch source inputs."""
        return await invoke(simulation_inputs.close, simulationId, coverage=("simulation_input_release",))

    @register(readonly=False)
    async def capture_library_open(sourceLibrary: str) -> ToolResult:
        """Copy one allowed OLB and read package/device/cell/part/pin definitions in an isolated Dbo worker. Pin numbers are device mappings, not symbol positions. No library mutation or footprint existence check."""
        return await invoke(library.open, sourceLibrary, backend="capture_dbo",
                            coverage=("olb_device_definition_read",),
                            not_checked=("library_write", "dsn_cache_sync", "external_footprint"))

    @register(readonly=True)
    async def capture_library_query(libraryId: str, entity: Literal["package", "device", "cell", "part", "pin"],
                                    packageName: str | None = None, cursor: str | None = None,
                                    limit: Annotated[int, Field(ge=1, le=1000)] = 100) -> ToolResult:
        """Page immutable library definitions; exact optional package name, revision-bound cursors, no native pointers. Cell IDs are device-scoped views, not globally deduplicated library identities."""
        return await invoke(library.query, libraryId, entity, packageName, cursor, limit,
                            backend="capture_dbo_snapshot", coverage=("olb_definition_query",))

    @register(readonly=True)
    async def capture_query_library_vectors(libraryId: str, partId: str, cursor: str | None = None,
            limit: Annotated[int, Field(ge=1, le=1000)] = 100) -> ToolResult:
        """Read basic typed vectors in native draw order for one revision-bound library part. Typed arrays include geometry/style/fill/hatch, text LOGFONT/default classification, and bitmap bounds/location/dimensions/DIB size/SHA256. Bitmap bytes are read in a fixed isolated worker; no native handle is returned. Unsupported kinds fail; no rendered appearance verdict."""
        return await invoke(query_library_vectors, library, libraryId, partId, cursor, limit,
                            backend="capture_dbo", coverage=("library_basic_vector_fields", "native_vector_order"),
                            not_checked=("rendered_appearance", "pin_label_fonts", "bitmap_nested_symbol"))

    @register(readonly=True)
    async def capture_query_net_symbols(libraryId: str, kind: Literal["global", "port", "offpage"] | None = None,
            cursor: str | None = None, limit: Annotated[int, Field(ge=1, le=1000)] = 100) -> ToolResult:
        """Read native global/port/offpage symbol names and host-validated type codes from an immutable OLB session. Snapshot-bound paging; no geometry, placement or electrical verdict."""
        return await invoke(query_net_symbols, library, libraryId, kind, cursor, limit, backend="capture_dbo", coverage=("net_symbol_source_identity", "native_kind_name_metadata"), not_checked=("symbol_geometry", "placement", "electrical_connectivity"))

    @register(readonly=False)
    async def capture_library_close(libraryId: str) -> ToolResult:
        """Release this server's copied-library cache; never save or delete a source OLB."""
        return await invoke(library.close, libraryId, coverage=("library_session_release",))

    @register(readonly=False)
    async def cadence_create_workspace(sourceDesign: str) -> ToolResult:
        """Copy one explicitly selected DSN from configured read roots; external project/library/model dependencies are not copied or verified."""
        return await invoke(capture.create_workspace, sourceDesign, coverage=("single_design_copy",),
                            not_checked=("external_dependencies", "project_closure"))

    @register(readonly=False)
    async def capture_open(workspaceId: str) -> ToolResult:
        """Read a registered DSN copy in an isolated Tcl worker; retain an immutable definition snapshot, not a live GUI or writable Dbo session."""
        return await invoke(capture.open, workspaceId, backend="capture_dbo",
                            coverage=("design_definitions", "pin_net_definitions"),
                            not_checked=("occurrence_connectivity", "external_dependencies", "save_reopen"))

    @register(readonly=True)
    async def capture_query(sessionId: str, entity: Literal["schematic", "page", "part", "pin"],
                            scope: Scope, fields: list[str] | None = None,
                            reference: str | None = None, cursor: str | None = None,
                            limit: Annotated[int, Field(ge=1, le=1000)] = 100) -> ToolResult:
        """Query immutable design definitions with exact reference filtering and revision-bound pagination; occurrence scopes and full hierarchical nets are unavailable."""
        return await invoke(capture.query, sessionId, entity, scope.model_dump(), fields, reference, cursor, limit,
                            backend="capture_dbo", coverage=("design_definitions",),
                            not_checked=("occurrence_connectivity", "external_dependencies"))

    @register(readonly=False)
    async def capture_get_hierarchy(sessionId: str, cursor: str | None = None,
                                    limit: Annotated[int, Field(ge=1, le=1000)] = 100) -> ToolResult:
        """Read and page occurrence structure and effective component-instance properties; identity is session/revision scoped; instancePathSegments use parent context and complete unit references, while native path/hierarchicalPath may repeat. Bounded traversal rejects cycles/limits instead of returning a truncated tree. Not occurrence-expanded pin/net verification."""
        return await invoke(get_hierarchy, capture, sessionId, cursor, limit, backend="capture_dbo",
                            coverage=("occurrence_structure", "instance_effective_properties"),
                            not_checked=("occurrence_pin_net_connectivity", "root_component_properties", "external_design_closure"))

    @register(readonly=False)
    async def capture_query_connections(sessionId: str, entity: Literal["wire", "alias", "global", "port", "offpage", "nc"],
                                         pageId: str | None = None, cursor: str | None = None,
                                         limit: Annotated[int, Field(ge=1, le=1000)] = 100) -> ToolResult:
        """Read bounded wire/alias/power/port/offpage/NC definitions and native coordinates, with optional exact pageId and revision-bound pagination. Does not infer junction, bus-member or occurrence connectivity."""
        return await invoke(query_objects, capture, sessionId, "connections", entity, pageId, cursor, limit,
                            backend="capture_dbo", coverage=("connection_object_definitions",),
                            not_checked=("junction_connectivity", "bus_member_connectivity", "occurrence_connectivity", "native_drc"))

    @register(readonly=False)
    async def capture_query_bus(sessionId: str, entity: Literal["bus", "scalar", "entry", "pin_member"],
                                pageId: str | None = None, cursor: str | None = None,
                                limit: Annotated[int, Field(ge=1, le=1000)] = 100) -> ToolResult:
        """Read bounded named bus members in native order, scalar branches and bus-entry geometry/direct wire references from a frozen DSN. Exact page filtering and session/query/page-size cursors; null entry endpoints remain explicit. pin_member additionally reads same-page definition pin/net membership using native HasMember/GetPosition/GetMember pointer identity, including false rows. Does not certify occurrence connectivity, routed completeness or nested Bundle semantics."""
        return await invoke(query_bus, capture, sessionId, entity, pageId, cursor, limit,
                            backend="capture_dbo", coverage=("native_named_bus_members", "native_entry_wire_references"),
                            not_checked=("physical_pin_member_connectivity", "occurrence_bus_connectivity", "nested_bundle_semantics", "native_drc"))

    @register(readonly=False)
    async def capture_plan_bus_create(sessionId: str, guiSessionId: str, hostProject: str, pageId: str,
                                      prefix: str, firstIndex: int, lastIndex: int,
                                      busStart: list[int], busEnd: list[int], branches: list[BusBranch],
                                      expectedConnections: list[PinExpectation], editorOccurrence: str | None = None) -> ToolResult:
        """Plan a simple contiguous2..128-member vertical bus and explicitly declared orthogonal scalar branches in a new DSN. Declare every page pin result and each entry's expected native bus attachment; partial/missing/off-bus routing is explicit and never a design-pass result. Existing named wire groups, entry references, aliases and connection objects must be preserved. No implicit net retargeting or Bundle source preservation."""
        return await invoke(bus_creates.plan, sessionId, guiSessionId, hostProject, pageId, prefix, firstIndex, lastIndex,
                            busStart, busEnd, [row.model_dump() for row in branches], [row.model_dump() for row in expectedConnections], editorOccurrence,
                            backend="capture_native_editor", coverage=("typed_bus_creation_plan", "explicit_pin_and_entry_expectations"),
                            not_checked=("save_reopen", "physical_pin_member_connectivity", "occurrence_bus_connectivity", "nested_bundle_semantics", "native_drc"))

    @register(readonly=False)
    async def capture_apply_bus_create(planId: str, planDigest: str,
                                       idempotencyKey: Annotated[str, Field(min_length=1, max_length=128)]) -> ToolResult:
        """Create the planned ordinary bus in an isolated PCB output through fixed native editor commands, close output, restore clean host and independently reopen all declared pins/named geometry/member order/entry links. Never replay a started job. Routing completeness is local entry structure; designPassed remains null."""
        return await invoke(bus_creates.apply, planId, planDigest, idempotencyKey, backend="capture_native_editor",
                            coverage=("native_bus_create", "independent_bus_reopen", "declared_native_entry_link_verification"),
                            not_checked=("physical_pin_member_connectivity", "occurrence_bus_connectivity", "nested_bundle_semantics", "native_drc", "rendered_layout"))

    @register(readonly=True)
    async def capture_bus_create_jobs(offset: Annotated[int, Field(ge=0, le=4096)] = 0,
                                      limit: Annotated[int, Field(ge=1, le=100)] = 100) -> ToolResult:
        """Page durable bus creation plans/jobs and failures; does not replay mutations."""
        return await invoke(bus_creates.jobs, offset, limit, coverage=("durable_bus_create_jobs",))

    @register(readonly=False)
    async def capture_cancel_bus_create(planId: str, planDigest: str) -> ToolResult:
        """Cancel only a pending bus task. Started Capture work is observe/recover only; never kill the host."""
        return await invoke(bus_creates.cancel, planId, planDigest, coverage=("pending_bus_cancel",))

    @register(readonly=False)
    async def capture_recover_bus_create(planId: str, planDigest: str) -> ToolResult:
        """Verify an existing bus result after proof the original forwarder stopped. No native mutation replay."""
        return await invoke(bus_creates.recover, planId, planDigest, backend="capture_native_editor",
                            coverage=("existing_bus_artifact_verification", "no_mutation_replay"),
                            not_checked=("physical_pin_member_connectivity", "occurrence_bus_connectivity", "nested_bundle_semantics", "native_drc"))

    @register(readonly=False)
    async def capture_query_graphics(sessionId: str, entity: Literal["part_bounds", "display_property", "graphic", "titleblock"],
                                      pageId: str | None = None, cursor: str | None = None,
                                      limit: Annotated[int, Field(ge=1, le=1000)] = 100) -> ToolResult:
        """Read native part/graphic/titleblock bounds, text and display-property layout. Display locations are owner-local; cached display bounds may be dirty and their coordinate space/rendered validity is not verified. No automatic clearance verdict."""
        return await invoke(query_objects, capture, sessionId, "graphics", entity, pageId, cursor, limit,
                            backend="capture_dbo", coverage=("graphic_object_definitions", "native_cached_bounds"),
                            not_checked=("rendered_bounds_validity", "display_bounds_coordinate_space", "automatic_clearance_verdict"))

    @register(readonly=True)
    async def capture_get_occurrence_properties(sessionId: str,
                                                occurrenceId: Annotated[str, Field(min_length=1, max_length=64)]) -> ToolResult:
        """Read one component occurrence's native effective/direct-user properties and its immediate definition's separate property layers and base/full device identity. Select by session/revision hierarchy occurrence ID and full unit path segments. Repeated schematic occurrences remain distinct. Root context properties are explicitly unavailable after a native crash; complete inheritance-source, display layers and connectivity remain unverified."""
        return await invoke(query_occurrence_properties, capture, sessionId, occurrenceId, backend="capture_dbo",
                            coverage=("component_occurrence_property_layers", "immediate_definition_layers", "full_unit_path_identity"),
                            not_checked=("root_context_properties", "complete_inheritance_source_resolution", "occurrence_pin_net_connectivity"))

    @register(readonly=True)
    async def capture_query_page_vectors(sessionId: str, pageId: str, cursor: str | None = None,
                                         limit: Annotated[int, Field(ge=1, le=1000)] = 100) -> ToolResult:
        """Read page comment graphics in native order: local typed vector descriptors, full text/font, instance pose and native-transformed page control points. Bitmap byte identity uses the fixed bounded worker. Unmodeled OLE/nested graphics remain explicit unsupported rows. Local text rectangles and control points are not rendered glyph bounds; symbol/titleblock vectors and electrical connectivity remain unchecked."""
        return await invoke(query_page_vectors, capture, sessionId, pageId, cursor, limit, backend="capture_dbo",
                            coverage=("typed_page_comment_vectors", "local_descriptor_and_native_page_control_points", "explicit_unsupported_inventory"),
                            not_checked=("rendered_text_bounds", "symbol_and_titleblock_vectors", "electrical_connectivity", "native_drc"))

    @register(readonly=True)
    async def capture_query_part_vectors(sessionId: str, partId: str, cursor: str | None = None,
            limit: Annotated[int, Field(strict=True, ge=1, le=1000)] = 100) -> ToolResult:
        """Read actual defining-part vectors in native order and native-transformed page control points. IDs use revision/part/vector index; nativeId is null because defining vectors have no accepted native ID. Includes typed text/font and bitmap identity; unsupported graphics remain explicit. Cached instance boxes are not used as actual vector extents. Does not certify rendered clearance, display properties, pin graphics or occurrence geometry."""
        return await invoke(query_part_vectors,capture,sessionId,partId,cursor,limit,backend="capture_dbo",
                            coverage=("typed_defining_part_vectors","native_page_control_points","explicit_unsupported_inventory"),
                            not_checked=("rendered_clearance","display_properties_and_pin_graphics","occurrence_geometry","native_drc"))

    @register(readonly=True)
    async def capture_check_symbol_contacts(sessionId: str, partId: str) -> ToolResult:
        """Find exact crossing/T/overlap and strictly-contained-segment candidates between one part's actual linear defining vectors and same-page wires. Simple closed box/polygon outlines are checked; non-simple containment is explicit skipped. Curves/text/bitmap/fill are explicit skipped rows. Does not measure glyph/stroke clearance, shared endpoints, non-simple closed-shape containment, pin connectivity or DRC; never reports a design pass. Source revision, traversal and pair/finding budgets are enforced."""
        return await invoke(check_symbol_contacts,capture,sessionId,partId,backend="capture_dbo",
                            coverage=("exact_linear_symbol_wire_contacts","simple_closed_outline_containment","page_isolation","explicit_skipped_geometry"),
                            not_checked=("rendered_clearance","electrical_connectivity","native_drc"))

    @register(readonly=True)
    async def capture_get_page_dimensions(sessionId: str, pageId: str) -> ToolResult:
        """Read native page physical parameters, document dimensions, unit scale and border flags. FullPageBounds uses native document coordinates. Zero-size pages return dimensionsKnown=false; printable origin and glyph bounds are not certified."""
        return await invoke(query_page_dimensions,capture,sessionId,pageId,backend="capture_dbo",coverage=("native_page_size_units_and_flags",),not_checked=("physical_printable_origin", "glyph_bounds"))

    @register(readonly=True)
    async def capture_check_page_graphic_bounds(sessionId: str, pageId: str,
            margin: Annotated[int, Field(strict=True, ge=0, le=1000000)] = 0) -> ToolResult:
        """Check all supported page comment-graphic declared control points against native full-page dimensions and an explicit margin. Exact edges are inside. Findings are candidates, not actual glyph/curve clipping or DRC. Zero-size/unsupported/over-budget pages fail explicitly; no partial success."""
        return await invoke(check_page_graphic_bounds,capture,sessionId,pageId,margin,backend="capture_dbo",coverage=("declared_comment_control_point_bounds",),not_checked=("rendered_glyph_bounds", "curve_clipping", "parts_and_wires", "native_drc"))

    @register(readonly=False)
    async def capture_get_part_geometry(sessionId: str, partId: str) -> ToolResult:
        """Read native part location/rotation/mirror codes and actual transformed pin hotspots from a fresh Dbo process. Revision and pin identities must match this immutable definition session; does not assess wiring or rendered text."""
        return await invoke(read_part_geometry, capture, sessionId, partId, backend="capture_dbo",
                            coverage=("part_placement", "actual_pin_hotspots"),
                            not_checked=("electrical_connectivity", "rendered_text_clearance", "occurrence_geometry"))

    @register(readonly=True)
    async def capture_get_display_font(sessionId: str, partId: str,
                                      property: Annotated[str, Field(min_length=1, max_length=128)]) -> ToolResult:
        """Read the complete effective LOGFONT and default-font inheritance flag for one existing instance display property. Unit identity is native-id bound; rendered bounds and font availability are not certified."""
        return await invoke(query_font, capture, sessionId, partId, property, backend="capture_dbo", coverage=("native_display_font", "font_default_flag"))

    @register(readonly=False)
    async def capture_plan_display_font(sessionId: str, partId: str,
                                       property: Annotated[str, Field(min_length=1, max_length=128)], font: VectorFont) -> ToolResult:
        """Plan a complete explicit font replacement on an existing display property. Unspecified font fields take schema defaults. Require native identity, source and frozen state; verify all instance fonts/default flags and modeled geometry/properties/connections after independent reopen. Cadence-normalized values are rejected rather than silently accepted. No font rendering guarantee."""
        return await invoke(display_fonts.plan, sessionId, partId, property, font.model_dump(), backend="capture_dbo", coverage=("explicit_display_font_plan", "all_display_font_baseline"))

    @register(readonly=False)
    async def capture_apply_display_font(planId: str, planDigest: str,
                                         idempotencyKey: Annotated[str, Field(min_length=1, max_length=200)]) -> ToolResult:
        """Apply one immutable display-font plan to a new DSN copy, then independently reopen and verify. Never replay a started write."""
        return await invoke(display_fonts.apply, planId, planDigest, idempotencyKey, backend="capture_dbo", coverage=("native_display_font_write", "independent_all_font_and_state_verification"))

    @register(readonly=True)
    async def capture_display_font_jobs(offset: Annotated[int, Field(ge=0, le=4096)] = 0,
                                        limit: Annotated[int, Field(ge=1, le=100)] = 50) -> ToolResult:
        """Inspect persisted display-font tasks."""
        return await invoke(display_fonts.jobs, offset, limit)

    @register(readonly=False)
    async def capture_cancel_display_font(planId: str, planDigest: str) -> ToolResult:
        """Cancel a pending or owned running font task; never affect another process."""
        return await invoke(display_fonts.cancel, planId, planDigest)

    @register(readonly=False)
    async def capture_recover_display_font(planId: str, planDigest: str) -> ToolResult:
        """Verify existing stopped font output without repeating the native write."""
        return await invoke(display_fonts.recover, planId, planDigest, backend="capture_dbo", not_checked=("native_completion",))

    @register(readonly=False)
    async def capture_plan_display_property(sessionId: str, partId: str,
                                             propertyName: Annotated[str, Field(min_length=1, max_length=128)],
                                             location: Annotated[list[int], Field(min_length=2, max_length=2)] | None = None,
                                             rotationCode: Annotated[int, Field(ge=0, le=3)] | None = None,
                                             displayTypeCode: Annotated[int, Field(ge=0, le=4)] | None = None) -> ToolResult:
        """Plan existing display-property owner-local position, native rotation and display type changes. Type codes: 0 hidden, 1 value, 2 name/value, 3 name, 4 both-if-valued. Data/reference values and unrelated displays must stay intact. Font editing is not yet available."""
        return await invoke(display_properties.plan, sessionId, partId, propertyName, location, rotationCode, displayTypeCode,
                            coverage=("display_layout_plan",), not_checked=("save_reopen", "font_descriptor", "rendered_text_bounds"))

    @register(readonly=False)
    async def capture_apply_display_property(planId: str, planDigest: str,
                                              idempotencyKey: Annotated[str, Field(min_length=1, max_length=128)]) -> ToolResult:
        """Save planned display layout in a new isolated DSN and independently read it back; preserve data properties, unrelated displays and definition pin nets. Mark cached bounds dirty; no rendered-clearance/font verdict."""
        return await invoke(display_properties.apply, planId, planDigest, idempotencyKey, backend="capture_dbo",
                            coverage=("display_layout_save_reopen", "data_property_preservation", "definition_baseline_preservation"),
                            not_checked=("font_descriptor", "rendered_text_bounds", "occurrence_connectivity", "native_drc"))

    @register(readonly=True)
    async def capture_display_property_jobs(offset: Annotated[int, Field(ge=0, le=4096)] = 0,
                                             limit: Annotated[int, Field(ge=1, le=100)] = 100) -> ToolResult:
        """Page durable isolated display-layout plans/jobs without replay."""
        return await invoke(display_properties.jobs, offset, limit, coverage=("durable_display_property_jobs",))

    @register(readonly=False)
    async def capture_cancel_display_property(planId: str, planDigest: str) -> ToolResult:
        """Cancel a pending display-layout plan or signal this server's active owned worker; source is unchanged and partial output retained."""
        return await invoke(display_properties.cancel, planId, planDigest, coverage=("owned_display_property_cancel",))

    @register(readonly=False)
    async def capture_recover_display_property(planId: str, planDigest: str) -> ToolResult:
        """Verify an existing interrupted display-layout output after proof its worker stopped. Never replay; native completion remains unverified after recovery."""
        return await invoke(display_properties.recover, planId, planDigest, backend="capture_dbo",
                            coverage=("existing_display_artifact_verification",), not_checked=("native_completion", "font_descriptor", "rendered_text_bounds"))

    @register(readonly=False)
    async def capture_plan_cache_replace(sessionId: str, partId: str, libraryId: str, packageId: str,
            expectedInstances: Annotated[list[CacheReplacementInstance], Field(min_length=1, max_length=64)]) -> ToolResult:
        """Plan compatible replacement of the exact source-qualified cache package and every bound instance in a new DSN copy. Declare every affected partId, replacement libraryPartId and complete expected pin/hotspot/net table. Physical pad numbers, package size and device designators stay compatible; connectivity changes, external design parts and typed/source-binding user overrides are refused. Freezes design/library/oracles and modeled identity, effective/user/display state, all instance geometry, cache metadata and connection objects. Full inheritance origins, fonts/rendering and occurrence nets are not certified."""
        return await invoke(cache_replacements.plan,sessionId,partId,libraryId,packageId,
                            [row.model_dump() for row in expectedInstances],backend="capture_dbo",
                            coverage=("source_qualified_cache_replace_plan","complete_affected_group_pin_expectations"),
                            not_checked=("save_reopen","full_inheritance_origin","occurrence_connectivity","native_drc"))

    @register(readonly=False)
    async def capture_apply_cache_replace(planId: str, planDigest: str,
            idempotencyKey: Annotated[str, Field(min_length=1,max_length=128)]) -> ToolResult:
        """Replace a cache once on exclusive owned DSN/OLB copies, restore explicit references/string overrides, save and independently reopen all modeled preservation graphs and actual source views. Started mutations never replay; only verified output may be opened with kind=cache_replace."""
        return await invoke(cache_replacements.apply,planId,planDigest,idempotencyKey,backend="capture_dbo",
                            coverage=("owned_cache_replace_save_reopen","source_qualified_cache_and_instance_preservation"),
                            not_checked=("full_inheritance_origin","occurrence_connectivity","native_drc","electrical_behavior"))

    @register(readonly=True)
    async def capture_cache_replace_jobs(offset: Annotated[int,Field(ge=0,le=4096)]=0,
            limit: Annotated[int,Field(ge=1,le=100)]=50) -> ToolResult:
        """List durable compatible cache replacement task states."""
        return await invoke(cache_replacements.jobs,offset,limit,coverage=("durable_cache_replace_jobs",))

    @register(readonly=False)
    async def capture_cancel_cache_replace(planId: str, planDigest: str) -> ToolResult:
        """Cancel an unstarted task or request stop of this server's owned cache replacement worker."""
        return await invoke(cache_replacements.cancel,planId,planDigest,coverage=("cache_replace_cancel",))

    @register(readonly=False)
    async def capture_recover_cache_replace(planId: str, planDigest: str) -> ToolResult:
        """After proving the prior worker stopped, verify existing cache replacement bytes only. Never replay replacement or restore missing artifacts."""
        return await invoke(cache_replacements.recover,planId,planDigest,backend="capture_dbo",coverage=("verify_existing_cache_replace_output",))

    @register(readonly=True)
    async def capture_query_cache_binding(sessionId: str, partId: str) -> ToolResult:
        """Read a placed definition's exact DSN cache package by its stored source library and package name. Cross-check native GetCachedPackage identity with the actual placed package, two origin readers and independent instance inventory. Returns only the selected package definitions and distinguishes same-name local/cache entries. Does not open the external source library or certify cache synchronization."""
        return await invoke(query_cache_binding, capture, sessionId, partId, backend="capture_dbo",
                            coverage=("source_qualified_cache_package_identity", "placed_package_and_independent_inventory_match"),
                            not_checked=("external_library_file_identity", "cache_write_or_replacement", "occurrence_connectivity", "native_drc"))

    @register(readonly=True)
    async def capture_query_cache(sessionId: str, entity: Literal["package", "device", "cell", "part", "pin"],
                                   packageName: str | None = None, cursor: str | None = None, limit: int = 100) -> ToolResult:
        """Read the bound DSN's design cache definitions, not an external OLB. Object IDs and cursors belong to this immutable session. Does not prove source-library identity, cache synchronization or external-dependency closure."""
        return await invoke(query_cache, capture, sessionId, entity, packageName, cursor, limit,
                            backend="capture_dbo", coverage=("dsn_cache_definition_query",),
                            not_checked=("source_olb_identity", "cache_synchronization", "embedded_cache_closure"))

    @register(readonly=False)
    async def capture_plan_cached_unit_add(sessionId: str, ownerPartId: str, cachePartId: str,
                                            location: list[int], expectedPins: Annotated[list[PlacementPin], Field(min_length=1, max_length=500)],
                                            expectedExistingConnections: Annotated[list[ExistingUnitPin], Field(max_length=2048)],
                                            rotationCode: Annotated[int, Field(ge=0, le=3)] = 0,
                                            mirrorCode: Annotated[int, Field(ge=0, le=1)] = 0,
                                            targetPageId: str | None = None) -> ToolResult:
        """Plan one missing device of an existing physical package on its owner page or an explicit targetPageId in the same schematic using a revision-bound cache partId from capture_query_cache. Retains the owner base reference and consistent group Value/Footprint, rejects an occupied device/full reference or conflicting package ownership. Declare every new pin/hotspot/net and existing page pinId. Cross-page plans additionally freeze every original modeled instance geometry and effective/user/display property layer. No external OLB import or new wires. Apply/cancel/recover/open with the existing multiunit placement task family."""
        return await invoke(multiunit_placements.plan_add, sessionId, ownerPartId, cachePartId, location,
                            rotationCode, mirrorCode, [p.model_dump() for p in expectedPins],
                            [p.model_dump() for p in expectedExistingConnections], targetPageId, coverage=("existing_cache_missing_unit_plan",),
                            not_checked=("save_reopen", "cross_page_unit_assignment", "flat_occurrence_connectivity"))

    @register(readonly=False)
    async def capture_plan_multiunit_placement(sessionId: str, pageId: str, libraryId: str,
                                               reference: str, value: str,
                                               units: Annotated[list[MultiunitPlacement], Field(min_length=2, max_length=16)],
                                               expectedExistingConnections: Annotated[list[ExistingUnitPin], Field(max_length=2048)]) -> ToolResult:
        """Plan all devices of one OLB package under one new base reference on one qualified page. Select one source part per device and declare each unit's full pose/pin/net oracle. Existing page pins use revision-bound pinId, so repeated base references and shared pin numbers remain distinct. Shared physical pads require consistent per-unit net expectations; unresolved local/flat contradictions are refused. Creates no wires; existing connection objects must be preserved. Pin/basic-vector geometry/style/font identity; bitmap and symbol-vector types still refused."""
        return await invoke(multiunit_placements.plan, sessionId, pageId, libraryId, reference, value,
                            [u.model_dump() for u in units], [p.model_dump() for p in expectedExistingConnections],
                            coverage=("atomic_complete_package_plan",), not_checked=("save_reopen", "flat_occurrence_connectivity"))

    @register(readonly=False)
    async def capture_apply_multiunit_placement(planId: str, planDigest: str,
                                                idempotencyKey: Annotated[str, Field(min_length=1, max_length=128)]) -> ToolResult:
        """Execute a complete source-package placement or planned missing-device addition from the existing cache. The complete-package path copies DSN/OLB and imports one new cache; the missing-device path copies only DSN and preserves its cache. Independently reopen to verify full references, unit-scoped pins/nets/hotspots, Value/Footprint, connection objects and original page geometry. Complete groups compare source pin/basic-vector views; missing units verify the selected cached view name and unchanged cache pin metadata. No cross-page assignment, full graphic cache, flat/occurrence or DRC certification."""
        return await invoke(multiunit_placements.apply, planId, planDigest, idempotencyKey, backend="capture_dbo", coverage=("complete_package_save_reopen", "unit_scoped_pin_identity"), not_checked=("flat_occurrence_connectivity", "native_drc"))

    @register(readonly=True)
    async def capture_multiunit_placement_jobs(offset: Annotated[int, Field(ge=0, le=4096)] = 0,
                                               limit: Annotated[int, Field(ge=1, le=100)] = 50) -> ToolResult:
        """List durable complete-package placement jobs."""
        return await invoke(multiunit_placements.jobs, offset, limit)

    @register(readonly=False)
    async def capture_cancel_multiunit_placement(planId: str, planDigest: str) -> ToolResult:
        """Cancel a pending or running owned complete-package placement; retain evidence."""
        return await invoke(multiunit_placements.cancel, planId, planDigest)

    @register(readonly=False)
    async def capture_recover_multiunit_placement(planId: str, planDigest: str) -> ToolResult:
        """Verify a retained complete-package output without repeating native writes."""
        return await invoke(multiunit_placements.recover, planId, planDigest, backend="capture_dbo", coverage=("verify_only_group_recovery",))

    @register(readonly=False)
    async def capture_plan_placement(sessionId: str, pageId: str, libraryId: str, libraryPartId: str,
                                      reference: str, location: list[int], value: str,
                                      expectedPins: list[PlacementPin], expectedExistingConnections: list[PinExpectation],
                                      rotationCode: int = 0, mirrorCode: int = 0,
                                      expectedWirePaths: list[list[list[int]]] | None = None) -> ToolResult:
        """Plan a new uniquely referenced instance from an immutable OLB part/device. Declare every new pin's number/name/global hotspot/net and all existing page pin expectations. Verify raw pose without inferring a rotation transform. New private cache package, never replace an existing cache. Multiple source views require an unambiguous source name or pin/basic-vector identity including box/ellipse/arc/ordered polygon/polyline/bezier/fill/text-font fields; other vector kinds are refused. Shared-reference additional units require a dedicated operation."""
        return await invoke(placements.plan, sessionId, pageId, libraryId, libraryPartId, reference, location,
                            rotationCode, mirrorCode, value, [r.model_dump() for r in expectedPins],
                            [r.model_dump() for r in expectedExistingConnections], expectedWirePaths,
                            coverage=("library_bound_placement_plan", "explicit_global_hotspot_expectations"),
                            not_checked=("save_reopen", "embedded_cache_closure", "native_drc"))

    @register(readonly=False)
    async def capture_apply_placement(planId: str, planDigest: str,
                                      idempotencyKey: Annotated[str, Field(min_length=1, max_length=128)]) -> ToolResult:
        """Copy DSN and OLB, import a new cache package, place, save and independently reopen. Verify planned pin maps/nets/global hotspots, pose, value, footprint and connection-object preservation. For multiple source views, compare selected source and saved instance pin/basic-vector fields and native draw order in a fresh process. Does not prove bitmap/symbol-vector identity, rendered layout or other unmodeled attributes, external-library-independent cache closure or occurrence behavior."""
        return await invoke(placements.apply, planId, planDigest, idempotencyKey, backend="capture_dbo",
                            coverage=("placement_save_reopen", "explicit_pin_hotspots_and_bindings", "value_and_footprint"),
                            not_checked=("embedded_cache_closure", "shared_package_unit_lifecycle", "occurrence_connectivity", "native_drc"))

    @register(readonly=True)
    async def capture_placement_jobs(offset: Annotated[int, Field(ge=0, le=4096)] = 0,
                                      limit: Annotated[int, Field(ge=1, le=100)] = 100) -> ToolResult:
        """Page durable placement plans/jobs, without mutation replay."""
        return await invoke(placements.jobs, offset, limit, coverage=("durable_placement_jobs",))

    @register(readonly=False)
    async def capture_cancel_placement(planId: str, planDigest: str) -> ToolResult:
        """Cancel a pending placement or signal this server's active owned native worker; keep isolated evidence."""
        return await invoke(placements.cancel, planId, planDigest, coverage=("owned_placement_cancel",))

    @register(readonly=False)
    async def capture_recover_placement(planId: str, planDigest: str) -> ToolResult:
        """Only verify an existing placement output after proof the original worker stopped; no mutation replay or native completion claim."""
        return await invoke(placements.recover, planId, planDigest, backend="capture_dbo",
                            coverage=("existing_placement_artifact_verification",), not_checked=("native_completion", "embedded_cache_closure", "native_drc"))

    @register(readonly=False)
    async def capture_plan_pspice_netlist(sessionId: str, guiSessionId: str, sourceProject: str, sourceProfile: str) -> ToolResult:
        """Freeze an allowed same-directory single-DSN/single-profile project using a definition-session DSN snapshot and an explicit authenticated clean Capture host. No export yet; unsupported hierarchy/resource paths are refused."""
        return await invoke(native_netlists.plan, sessionId, guiSessionId, sourceProject, sourceProfile, backend="capture_gui",
                            coverage=("frozen_project_roles", "bound_native_host_plan"), not_checked=("complete_hierarchy_model_closure", "solver", "drc"))

    @register(readonly=False)
    async def capture_apply_pspice_netlist(planId: str, planDigest: str,
            idempotencyKey: Annotated[str, Field(min_length=1, max_length=128)]) -> ToolResult:
        """Generate new private NET/ALS once with fixed Tcl. Require real host PID/nonce completion, empty native error log and unchanged inputs/active context. A missing completion retains its host fence; never resend that task."""
        return await invoke(native_netlists.apply, planId, planDigest, idempotencyKey, backend="capture_gui",
                            coverage=("native_net_als_generation", "native_completion_receipt", "input_and_host_preservation"), not_checked=("complete_hierarchy_model_closure", "solver", "drc"))

    @register(readonly=True)
    async def capture_pspice_netlist_jobs(offset: Annotated[int, Field(ge=0, le=4096)] = 0,
                                          limit: Annotated[int, Field(ge=1, le=100)] = 50) -> ToolResult:
        """Page native NET/ALS task states and failures without starting a native operation."""
        return await invoke(native_netlists.jobs, offset, limit, coverage=("durable_native_netlist_jobs",))

    @register(readonly=False)
    async def capture_cancel_pspice_netlist(planId: str, planDigest: str) -> ToolResult:
        """Cancel only a not-yet-dispatched native NET/ALS plan. A started host call is too late to cancel; never terminate Capture as task cancellation."""
        return await invoke(native_netlists.cancel, planId, planDigest, coverage=("pending_native_plan_cancel",))

    @register(readonly=False)
    async def capture_recover_pspice_netlist(planId: str, planDigest: str) -> ToolResult:
        """Verify existing native receipt/NET/ALS after proof the original forwarder stopped. Release only the matching completed host fence; no regeneration or automatic host retargeting."""
        return await invoke(native_netlists.recover, planId, planDigest, backend="capture_gui",
                            coverage=("existing_native_netlist_verification", "no_mutation_replay"), not_checked=("complete_hierarchy_model_closure", "solver", "drc"))

    @register(readonly=False)
    async def capture_plan_design_create(rootName: Annotated[str, Field(min_length=1, max_length=64)],
                                          pageName: Annotated[str, Field(min_length=1, max_length=64)]) -> ToolResult:
        """Plan a new empty DSN with one declared root schematic and page, with no existing source design. ASCII names only until non-ASCII native save/reopen is verified. Does not create an OPJ, overwrite an existing design, or imply design/DRC approval."""
        return await invoke(design_creates.plan, rootName, pageName, backend="capture_dbo",
                            coverage=("new_design_declaration",), not_checked=("opj_project", "non_ascii_design_names", "native_drc"))

    @register(readonly=False)
    async def capture_apply_design_create(planId: str, planDigest: str,
                                          idempotencyKey: Annotated[str, Field(min_length=1, max_length=200)]) -> ToolResult:
        """Create one new isolated design, save and independently verify declared definitions, native root and recognized page object counts. sourceFingerprint is a declaration digest, not a prior design-file fingerprint. No started creation is replayed."""
        return await invoke(design_creates.apply, planId, planDigest, idempotencyKey, backend="capture_dbo",
                            coverage=("new_design_save_reopen", "declared_root_empty_page"),
                            not_checked=("opj_project", "custom_plugin_objects", "native_drc"))

    @register(readonly=True)
    async def capture_design_create_jobs(offset: Annotated[int, Field(ge=0, le=4096)] = 0,
                                          limit: Annotated[int, Field(ge=1, le=100)] = 50) -> ToolResult:
        """List durable new-design creation jobs."""
        return await invoke(design_creates.jobs, offset, limit, coverage=("durable_design_create_jobs",))

    @register(readonly=False)
    async def capture_cancel_design_create(planId: str, planDigest: str) -> ToolResult:
        """Cancel a pending or currently owned new-design creation job."""
        return await invoke(design_creates.cancel, planId, planDigest, coverage=("owned_design_create_cancel",))

    @register(readonly=False)
    async def capture_recover_design_create(planId: str, planDigest: str) -> ToolResult:
        """Verify existing stopped design creation bytes only; never repeat creation."""
        return await invoke(design_creates.recover, planId, planDigest, backend="capture_dbo",
                            coverage=("existing_created_design_verification",), not_checked=("native_completion", "native_drc"))

    @register(readonly=False)
    async def capture_plan_reference_map(sessionId: str,
                                         mappings: Annotated[list[ReferenceChange], Field(min_length=1, max_length=64)]) -> ToolResult:
        """Plan explicit reference renames/swaps for uniquely referenced single-unit placed definitions. Preserve the existing prefix and pin/net bindings; check final conflicts against unmapped parts. Uses collision-free temporary references for cycles. Multiunit, external, repeated/occurrence and unnumbered automatic allocation are refused or unavailable; not native automatic annotation."""
        return await invoke(reference_edits.plan, sessionId, [r.model_dump() for r in mappings], backend="capture_dbo",
                            coverage=("explicit_reference_mapping", "definition_conflicts_and_package_identity"),
                            not_checked=("multiunit_package_mapping", "occurrence_reference_mapping", "native_drc"))

    @register(readonly=False)
    async def capture_plan_package_reference_map(sessionId: str,
                                         mappings: Annotated[list[ReferenceChange], Field(min_length=1, max_length=64)]) -> ToolResult:
        """Plan whole physical-package base-reference renames/swaps. Each representative expands all placed units in its schematic, including units on other pages. Require verified source-qualified cache ownership and consistent shared pads; preserve NC ownership, complete modeled instance state and old/new pin-node tables. Explicit numbered references only; occurrence mapping and automatic annotation remain unavailable. Apply using capture_apply_reference_map."""
        return await invoke(reference_edits.plan_packages, sessionId, [r.model_dump() for r in mappings], backend="capture_dbo",
                            coverage=("explicit_package_reference_mapping", "unit_ownership", "old_new_pin_node_table", "modeled_instance_state", "nc_ownership"),
                            not_checked=("occurrence_reference_mapping", "native_automatic_annotation", "native_drc"))

    @register(readonly=False)
    async def capture_apply_reference_map(planId: str, planDigest: str,
                                          idempotencyKey: Annotated[str, Field(min_length=1, max_length=200)]) -> ToolResult:
        """Apply one fixed reference map in a new copy via temporary then final names, save and independently verify all definition pin nets, connection objects and affected-page poses/hotspots. Do not replay started writes or certify occurrence nets/display rendering."""
        return await invoke(reference_edits.apply, planId, planDigest, idempotencyKey, backend="capture_dbo",
                            coverage=("reference_save_reopen", "definition_pin_net_and_geometry_invariants"),
                            not_checked=("multiunit_package_mapping", "occurrence_connectivity", "display_text_rendering", "native_drc"))

    @register(readonly=True)
    async def capture_reference_jobs(offset: Annotated[int, Field(ge=0, le=4096)] = 0,
                                      limit: Annotated[int, Field(ge=1, le=100)] = 50) -> ToolResult:
        """List durable isolated reference mapping jobs."""
        return await invoke(reference_edits.jobs, offset, limit, coverage=("durable_reference_jobs",))

    @register(readonly=False)
    async def capture_cancel_reference_map(planId: str, planDigest: str) -> ToolResult:
        """Cancel a pending or currently owned fixed reference map, leaving source unchanged."""
        return await invoke(reference_edits.cancel, planId, planDigest, coverage=("owned_reference_map_cancel",))

    @register(readonly=False)
    async def capture_recover_reference_map(planId: str, planDigest: str) -> ToolResult:
        """Verify existing stopped map bytes only; never repeat temporary/final reference mutation."""
        return await invoke(reference_edits.recover, planId, planDigest, backend="capture_dbo",
                            coverage=("existing_reference_map_verification",), not_checked=("native_completion", "native_drc"))

    @register(readonly=False)
    async def capture_plan_part_edit(sessionId: str, partId: str, operation: Literal["set_pose", "delete"],
                                     expectedConnections: list[PinExpectation], location: list[int] | None = None,
                                     rotation: Annotated[int, Field(ge=0, le=3)] | None = None,
                                     mirror: Annotated[int, Field(ge=0, le=1)] | None = None,
                                     expectedPins: list[PartHotSpot] | None = None,
                                     expectedUnitConnections: Annotated[list[ExistingUnitPin], Field(max_length=2048)] | None = None) -> ToolResult:
        """Plan a definition-level part pose or deletion in a new copy. Declare all remaining page pin-net expectations and, for pose, every target global hotspot. Preserves wires and other connection objects, checks all page part poses. For a multiunit target, pass expectedConnections=[] and expectedUnitConnections covering remaining page pinIds; native ID/full unit ownership, cache pin metadata, Value/footprint and native page networks are additionally checked. Attached NC, implicit wire dragging and flat/occurrence certification remain unavailable. Rotation/mirror need explicit validated hotspots; no automatic affine oracle."""
        return await invoke(part_edits.plan, sessionId, partId, operation,
                            [p.model_dump() for p in expectedConnections], location, rotation, mirror,
                            None if expectedPins is None else [p.model_dump() for p in expectedPins],
                            None if expectedUnitConnections is None else [p.model_dump() for p in expectedUnitConnections],
                            backend="capture_dbo", coverage=("part_edit_plan", "explicit_page_pin_and_hotspot_expectations"),
                            not_checked=("occurrence_connectivity", "native_drc", "rendered_layout"))

    @register(readonly=False)
    async def capture_apply_part_edit(planId: str, planDigest: str,
                                      idempotencyKey: Annotated[str, Field(min_length=1, max_length=200)]) -> ToolResult:
        """Execute one fixed part definition edit on a new copy, then independently reopen and verify explicit page nets, poses/hotspots and connection-object baseline. Started writes are never replayed."""
        return await invoke(part_edits.apply, planId, planDigest, idempotencyKey, backend="capture_dbo",
                            coverage=("part_edit_save_reopen", "explicit_page_geometry_and_nets"),
                            not_checked=("occurrence_connectivity", "native_drc", "rendered_layout"))

    @register(readonly=True)
    async def capture_part_edit_jobs(offset: Annotated[int, Field(ge=0, le=4096)] = 0,
                                      limit: Annotated[int, Field(ge=1, le=100)] = 50) -> ToolResult:
        """List durable isolated part pose/deletion jobs."""
        return await invoke(part_edits.jobs, offset, limit, coverage=("durable_part_edit_jobs",))

    @register(readonly=False)
    async def capture_cancel_part_edit(planId: str, planDigest: str) -> ToolResult:
        """Cancel a pending or currently owned part edit; source remains unchanged."""
        return await invoke(part_edits.cancel, planId, planDigest, coverage=("owned_part_edit_cancel",))

    @register(readonly=False)
    async def capture_recover_part_edit(planId: str, planDigest: str) -> ToolResult:
        """Verify existing stopped part edit bytes only; never repeat the mutation."""
        return await invoke(part_edits.recover, planId, planDigest, backend="capture_dbo",
                            coverage=("existing_part_edit_verification",), not_checked=("native_completion", "native_drc"))

    @register(readonly=False)
    async def capture_plan_graphic_line_add(sessionId: str, pageId: str, start: list[int], end: list[int]) -> ToolResult:
        """Plan one decorative graphic line with explicit global endpoints and zero rotation on a new DSN. Does not create an electrical wire. Verify all definition pin nets and connection objects, plus existing target-page line geometry. Style/width/color, other graphic types, page bounds and DRC are not checked."""
        return await invoke(graphic_lines.plan, sessionId, pageId, start, end, backend="capture_dbo",
                            coverage=("graphic_line_plan", "explicit_endpoints"), not_checked=("rendered_layout", "other_graphic_types", "native_drc"))

    @register(readonly=False)
    async def capture_apply_graphic_line_add(planId: str, planDigest: str,
                                            idempotencyKey: Annotated[str, Field(min_length=1, max_length=128)]) -> ToolResult:
        """Add a planned decorative line in an owned copy, save and independently reopen; no source mutation."""
        return await invoke(graphic_lines.apply, planId, planDigest, idempotencyKey, backend="capture_dbo",
                            coverage=("graphic_line_save_reopen", "definition_and_connection_baseline"), not_checked=("rendered_layout", "native_drc"))

    @register(readonly=True)
    async def capture_graphic_line_jobs(offset: Annotated[int, Field(ge=0, le=4096)] = 0,
                                         limit: Annotated[int, Field(ge=1, le=100)] = 50) -> ToolResult:
        """List durable decorative-line jobs without launching Capture."""
        return await invoke(graphic_lines.jobs, offset, limit, coverage=("durable_graphic_line_jobs",))

    @register(readonly=False)
    async def capture_cancel_graphic_line_add(planId: str, planDigest: str) -> ToolResult:
        """Cancel only the owned planned or active decorative-line operation."""
        return await invoke(graphic_lines.cancel, planId, planDigest, coverage=("owned_graphic_line_cancel",))

    @register(readonly=False)
    async def capture_recover_graphic_line_add(planId: str, planDigest: str) -> ToolResult:
        """Verify an existing stopped decorative-line artifact; never replay mutation."""
        return await invoke(graphic_lines.recover, planId, planDigest, backend="capture_dbo",
                            coverage=("existing_graphic_line_artifact_verification",), not_checked=("native_completion", "rendered_layout", "native_drc"))

    @register(readonly=False)
    async def capture_plan_graphic_text_add(sessionId: str, pageId: str,
            text: Annotated[str, Field(min_length=1, max_length=4096)],
            location: Annotated[list[Annotated[int, Field(strict=True, ge=-1000000, le=1000000)]], Field(min_length=2, max_length=2)],
            width: Annotated[int, Field(strict=True, ge=1, le=100000)],
            height: Annotated[int, Field(strict=True, ge=1, le=100000)], font: VectorFont,
            rotation: Annotated[int, Field(strict=True, ge=0, le=3)] = 0,
            mirror: Annotated[int, Field(strict=True, ge=0, le=1)] = 0) -> ToolResult:
        """Plan literal page text in a new copy. location is the page anchor; width/height are local declared box dimensions, not rendered glyph bounds. Preserve all supported page graphics and modeled existing instance state. Only font quality1 is accepted; no DRC or clipping verdict."""
        return await invoke(graphic_texts.plan, sessionId, pageId, text, location, width, height, rotation, mirror, font.model_dump(), backend="capture_dbo", coverage=("explicit_text_page_anchor", "ordered_modeled_graphic_preservation"), not_checked=("rendered_glyph_bounds", "native_drc"))

    @register(readonly=False)
    async def capture_plan_graphic_text_edit(sessionId: str, graphicId: str,
            operation: Literal["update", "delete"], change: GraphicTextChange | None = None) -> ToolResult:
        """Plan update or deletion of one text graphic ID from capture_query_page_vectors. Update requires a complete replacement including font and page anchor; delete forbids change. Uses the existing graphic_text task family, preserving all other modeled graphics/instances/connections on new copies."""
        return await invoke(graphic_texts.plan_edit, sessionId, graphicId, operation, None if change is None else change.model_dump(), backend="capture_dbo", coverage=("bound_text_graphic_update_delete_plan", "ordered_modeled_preservation"), not_checked=("rendered_glyph_bounds", "native_drc"))

    @register(readonly=False)
    async def capture_apply_graphic_text_add(planId: str, planDigest: str,
                                            idempotencyKey: Annotated[str, Field(min_length=1, max_length=128)]) -> ToolResult:
        """Apply a planned page text addition, update or deletion in an owned copy, save and independently reopen; no source mutation."""
        return await invoke(graphic_texts.apply, planId, planDigest, idempotencyKey, backend="capture_dbo",
                            coverage=("graphic_text_save_reopen", "modeled_graphics_instances_and_connections"), not_checked=("rendered_layout", "native_drc"))

    @register(readonly=True)
    async def capture_graphic_text_jobs(offset: Annotated[int, Field(ge=0, le=4096)] = 0,
                                         limit: Annotated[int, Field(ge=1, le=100)] = 50) -> ToolResult:
        """List durable page-text jobs without launching Capture."""
        return await invoke(graphic_texts.jobs, offset, limit, coverage=("durable_graphic_text_jobs",))

    @register(readonly=False)
    async def capture_cancel_graphic_text_add(planId: str, planDigest: str) -> ToolResult:
        """Cancel only the owned planned or active page-text operation."""
        return await invoke(graphic_texts.cancel, planId, planDigest, coverage=("owned_graphic_text_cancel",))

    @register(readonly=False)
    async def capture_recover_graphic_text_add(planId: str, planDigest: str) -> ToolResult:
        """Verify an existing stopped page-text artifact; never replay mutation."""
        return await invoke(graphic_texts.recover, planId, planDigest, backend="capture_dbo",
                            coverage=("existing_graphic_text_artifact_verification",), not_checked=("native_completion", "rendered_layout", "native_drc"))

    @register(readonly=True)
    async def capture_get_library_pin_style(libraryId: str, pinId: str) -> ToolResult:
        """Read eleven native symbol-pin flags for a revision-bound library pin and enumerate all shared symbol scopes. No rendered appearance, DSN cache or electrical-behavior verdict."""
        from .library_pin_style import query_style
        return await invoke(query_style, library, libraryId, pinId, backend="capture_dbo",
                            coverage=("native_symbol_pin_flags", "semantic_pin_scope"), not_checked=("rendered_pin_shape", "dsn_cache_or_instances", "electrical_behavior"))

    @register(readonly=False)
    async def capture_plan_library_pin_edit(libraryId: str, pinId: str,
                                            name: Annotated[str, Field(min_length=1, max_length=128)] | None = None,
                                            number: Annotated[str, Field(min_length=1, max_length=32)] | None = None,
                                            pinType: Annotated[int, Field(ge=0, le=7)] | None = None,
                                            hotSpot: Annotated[list[Annotated[int, Field(strict=True, ge=-1000000, le=1000000)]], Field(min_length=2, max_length=2)] | None = None,
                                            visible: Annotated[bool, Field(strict=True)] | None = None,
                                            startPoint: Annotated[list[Annotated[int, Field(strict=True, ge=-1000000, le=1000000)]], Field(min_length=2, max_length=2)] | None = None,
                                            style: LibraryPinStyleChange | None = None) -> ToolResult:
        """Plan a pin name/type/startPoint/hotSpot/visibility symbol edit or a device-local physical pad renumber in a new OLB copy. Preview shows all shared symbol rows affected; partial heterogeneous shared-pad function changes, duplicate pads and shared-pad renumbering are refused. Semantic package/device/cell/part/position identities survive reordered snapshots. Geometry/visibility edits freeze and verify all modeled vectors, declared pin starts and reference templates. Optional style changes long/clock/dot and independently verifies all11 native pin flags across the complete library; preserves modeled graphics and start points. Preview includes the derived global flag for visibility/type changes: power pins remain global, other pins become global when hidden. This symbol flag does not certify instance/flat connectivity. No existing OLB or DSN cache update."""
        return await invoke(library_pin_edits.plan, libraryId, pinId, name, number, pinType, hotSpot, visible, startPoint, style.model_dump(exclude_none=True) if style is not None else None, backend="capture_dbo",
                            coverage=("library_pin_edit_plan", "explicit_affected_symbol_and_device_rows"),
                            not_checked=("dsn_cache", "native_drc", "rendered_symbol") +
                            (("symbol_vector_graphics", "reference_template") if hotSpot is None and visible is None and startPoint is None and style is None else ()))

    @register(readonly=False)
    async def capture_apply_library_pin_edit(planId: str, planDigest: str,
                                             idempotencyKey: Annotated[str, Field(min_length=1, max_length=200)]) -> ToolResult:
        """Edit a new OLB copy once, save, independently reopen and compare every package/device/variant/pin metadata row through stable semantics. Geometry/visibility plans also compare modeled graphics, declared pin starts and reference templates. Other plans retain their original verification scope. DSN instances and electrical behavior are not certified. Started mutations are never replayed."""
        return await invoke(library_pin_edits.apply, planId, planDigest, idempotencyKey, backend="capture_dbo",
                            coverage=("library_pin_save_reopen", "semantic_device_definition_graph"),
                            not_checked=("symbol_vector_graphics", "dsn_cache", "native_drc"))

    @register(readonly=True)
    async def capture_library_pin_edit_jobs(offset: Annotated[int, Field(ge=0, le=4096)] = 0,
                                             limit: Annotated[int, Field(ge=1, le=100)] = 50) -> ToolResult:
        """List durable isolated library pin edit jobs; legacy ordinal plans are not automatically migrated or replayed."""
        return await invoke(library_pin_edits.jobs, offset, limit, coverage=("durable_library_pin_edit_jobs",))

    @register(readonly=False)
    async def capture_cancel_library_pin_edit(planId: str, planDigest: str) -> ToolResult:
        """Cancel a pending or this server's currently owned library pin edit."""
        return await invoke(library_pin_edits.cancel, planId, planDigest, coverage=("owned_library_pin_edit_cancel",))

    @register(readonly=False)
    async def capture_recover_library_pin_edit(planId: str, planDigest: str) -> ToolResult:
        """Verify existing stopped OLB bytes only. Never repeat an edit; legacy ordinal expectations require explicit migration."""
        return await invoke(library_pin_edits.recover, planId, planDigest, backend="capture_dbo",
                            coverage=("existing_library_pin_artifact_verification",), not_checked=("native_completion", "dsn_cache"))

    @register(readonly=False)
    async def capture_open_edited_library(planId: str, planDigest: str, kind: Literal["pin", "vector", "package"] = "pin") -> ToolResult:
        """Open only a verified, unchanged edited OLB as a fresh query/placement library session, including after server restart. Does not expand public read roots."""
        return await invoke({"pin":library_pin_edits,"vector":library_vector_edits,"package":library_package_edits}[kind].open_output, planId, planDigest, backend="capture_dbo",
                            coverage=("verified_edited_library_session",), not_checked=("dsn_cache", "external_footprint"))

    @register(readonly=False)
    async def capture_plan_library_vector_edit(libraryId: str, partId: str, vectorId: str,
            operation: Literal["update", "delete"], replacement: LibraryVector | None = None,
            bitmapGeometry: BitmapGeometry | None = None) -> ToolResult:
        """Plan an existing basic-vector update or deletion on a new OLB copy. Update takes a full same-kind basic-vector declaration and keeps draw position; delete removes only that position, including an existing bitmap. Untouched bitmap bytes are included in preservation checks. Bitmap geometry update uses bitmapGeometry with bounds, location and expectedDibSha256, preserving dimensions and pixel bytes. Bitmap creation uses the dedicated library-create declaration; pixel replacement remains unavailable. Preview includes all device/package references to the same named native part. Freeze complete modeled definition/vector/template/pin-start expectations. Unknown vectors refuse; unmodeled properties and rendering are not certified."""
        return await invoke(library_vector_edits.plan, libraryId, partId, vectorId, operation,
                            replacement.model_dump() if replacement is not None else None,
                            bitmapGeometry.model_dump() if bitmapGeometry is not None else None, backend="capture_dbo",
                            coverage=("bound_library_vector_edit_plan", "explicit_shared_view_effects"),
                            not_checked=("unmodeled_library_properties", "rendered_appearance", "dsn_cache"))

    @register(readonly=False)
    async def capture_apply_library_vector_edit(planId: str, planDigest: str,
            idempotencyKey: Annotated[str, Field(min_length=1, max_length=200)]) -> ToolResult:
        """Edit a new private OLB once; save, independently reopen and verify the declared change and all modeled untouched definitions/vectors in order. Started writes are never replayed."""
        return await invoke(library_vector_edits.apply, planId, planDigest, idempotencyKey, backend="capture_dbo",
                            coverage=("library_vector_edit_save_reopen", "modeled_library_preservation"),
                            not_checked=("rendered_appearance", "unmodeled_library_properties", "dsn_cache", "native_drc"))

    @register(readonly=True)
    async def capture_library_vector_edit_jobs(offset: Annotated[int, Field(ge=0, le=4096)] = 0,
            limit: Annotated[int, Field(ge=1, le=100)] = 50) -> ToolResult:
        """Page durable library vector edit jobs without starting native work."""
        return await invoke(library_vector_edits.jobs, offset, limit, coverage=("durable_library_vector_edit_jobs",))

    @register(readonly=False)
    async def capture_cancel_library_vector_edit(planId: str, planDigest: str) -> ToolResult:
        """Cancel a pending or this server's owned library vector edit worker; preserve partial evidence."""
        return await invoke(library_vector_edits.cancel, planId, planDigest, coverage=("owned_library_vector_edit_cancel",))

    @register(readonly=False)
    async def capture_recover_library_vector_edit(planId: str, planDigest: str) -> ToolResult:
        """Verify existing stopped OLB bytes against frozen vector change/preservation expectations without repeating edits."""
        return await invoke(library_vector_edits.recover, planId, planDigest, backend="capture_dbo",
                            coverage=("existing_library_vector_edit_verification",), not_checked=("native_completion", "rendered_appearance", "dsn_cache"))

    @register(readonly=True)
    async def capture_query_library_package_properties(libraryId: str, packageId: str) -> ToolResult:
        """Read fixed package template/designator, PCB library/footprint names and explicit user property text/type/editability flags from an immutable library snapshot. The Capture information model defines UserProp values as strings; built-in DBProps are separate typed attributes. Numeric and Boolean-looking user text is never auto-parsed. No external footprint or DSN cache verdict."""
        return await invoke(query_package_properties, library, libraryId, packageId, backend="capture_dbo",
                            coverage=("library_package_fields", "explicit_package_user_properties"), not_checked=("external_footprint", "dsn_cache"))

    @register(readonly=False)
    async def capture_plan_library_package_edit(libraryId: str, packageId: str,
            changes: LibraryPackageChanges | None = None,
            userProperties: Annotated[list[LibraryPackageUserChange], Field(max_length=64)] | None = None) -> ToolResult:
        """Plan fixed package field changes and explicit string user-property set/empty/delete on a new OLB copy. Native Capture UserProps are string storage by the information model, not a generic typed-property channel. Freeze all package properties and modeled definitions/vectors/template/pin starts. Package names, devices and pin mappings do not change; built-in property shadowing and typed/locked user edits are refused."""
        return await invoke(library_package_edits.plan, libraryId, packageId, changes.model_dump() if changes else {},
                            [v.model_dump() for v in userProperties] if userProperties else [], backend="capture_dbo",
                            coverage=("bound_library_package_edit_plan", "modeled_preservation_expectation"), not_checked=("external_footprint", "dsn_cache", "typed_user_property_edit"))

    @register(readonly=False)
    async def capture_apply_library_package_edit(planId: str, planDigest: str,
            idempotencyKey: Annotated[str, Field(min_length=1, max_length=200)]) -> ToolResult:
        """Edit one package in a new OLB copy once, save and independently verify requested fields plus all modeled untouched definitions/vectors and every package's explicit user properties. Started edits are never replayed."""
        return await invoke(library_package_edits.apply, planId, planDigest, idempotencyKey, backend="capture_dbo",
                            coverage=("library_package_save_reopen", "package_property_and_modeled_graph_verification"), not_checked=("external_footprint", "dsn_cache", "native_drc"))

    @register(readonly=True)
    async def capture_library_package_edit_jobs(offset: Annotated[int, Field(ge=0, le=4096)] = 0,
            limit: Annotated[int, Field(ge=1, le=100)] = 50) -> ToolResult:
        """List durable isolated package property edit jobs."""
        return await invoke(library_package_edits.jobs, offset, limit, coverage=("durable_library_package_edit_jobs",))

    @register(readonly=False)
    async def capture_cancel_library_package_edit(planId: str, planDigest: str) -> ToolResult:
        """Cancel a pending or this server's owned package-property edit worker."""
        return await invoke(library_package_edits.cancel, planId, planDigest, coverage=("owned_library_package_edit_cancel",))

    @register(readonly=False)
    async def capture_recover_library_package_edit(planId: str, planDigest: str) -> ToolResult:
        """Verify existing stopped package-edit output against frozen fields/preservation without repeating native mutation."""
        return await invoke(library_package_edits.recover, planId, planDigest, backend="capture_dbo",
                            coverage=("existing_library_package_edit_verification",), not_checked=("native_completion", "external_footprint", "dsn_cache"))

    @register(readonly=False)
    async def capture_plan_library_create(spec: LibraryCreationSpec | LibraryFamilySpec) -> ToolResult:
        """Plan one new OLB from a single package or a bounded package family. Pin names must be explicit nonempty literals; native auto-generated anonymous names are outside this exact-name declaration. Repeated exact cellName with distinct partName creates alternate symbol views; all views must preserve position/name/electrical-type functions, while geometry/visibility may differ. Device physical maps/shared pads/swap IDs and package footprint/template are independently verified. Optional typed vectors declare line/box/ellipse/arc/polygon/polyline/bezier/fill/text/bitmap in draw order after legacy lines. Bitmap creation requires an allowed sourceBmp path plus independent BMP/DIB SHA256, dimensions and DIB size; exact RGB24/RGB32 bottom-up BMP assets are validated and privately frozen before execution. Geometry/style/font fields are bounded. Text location is bounds top-left. Accepts one package or a packages family of 2..8 independent package variants with disjoint native cell/part namespaces. Total physical pad count is summed per package and excludes extra views; no DSN cache/instance update or external footprint geometry certification."""
        return await invoke(library_creates.plan, spec.model_dump(), backend="capture_dbo",
                            coverage=("declared_library_create_plan", "physical_logical_pin_map"), not_checked=("rendered_labels_fonts", "native_drc"))

    @register(readonly=False)
    async def capture_apply_library_create(planId: str, planDigest: str,
                                            idempotencyKey: Annotated[str, Field(min_length=1, max_length=128)]) -> ToolResult:
        """Create once in a new owned OLB, save and independently verify the declared graph and all declared basic vectors in draw order. Never overwrite a source or replay a started operation."""
        return await invoke(library_creates.apply, planId, planDigest, idempotencyKey, backend="capture_dbo",
                            coverage=("library_create_save_reopen", "declared_library_graph_verification"), not_checked=("electrical_simulation_model", "rendered_labels_fonts", "native_drc"))

    @register(readonly=True)
    async def capture_library_create_jobs(offset: Annotated[int, Field(ge=0, le=4096)] = 0,
                                           limit: Annotated[int, Field(ge=1, le=100)] = 50) -> ToolResult:
        """Page durable OLB creation jobs and errors without starting a native process."""
        return await invoke(library_creates.jobs, offset, limit, coverage=("durable_library_create_jobs",))

    @register(readonly=False)
    async def capture_cancel_library_create(planId: str, planDigest: str) -> ToolResult:
        """Cancel a pending or this server's active owned OLB creation worker; keep partial artifacts unverified."""
        return await invoke(library_creates.cancel, planId, planDigest, coverage=("owned_library_create_cancel",))

    @register(readonly=False)
    async def capture_recover_library_create(planId: str, planDigest: str) -> ToolResult:
        """Verify an existing stopped OLB without repeating creation; nativeCompletionVerified stays false on recovery."""
        return await invoke(library_creates.recover, planId, planDigest, backend="capture_dbo",
                            coverage=("existing_library_graph_verification",), not_checked=("native_completion", "native_drc"))

    @register(readonly=False)
    async def capture_open_created_library(planId: str, planDigest: str) -> ToolResult:
        """Register only a verified, hash-matching created OLB for normal library query/placement. Does not expand public read roots."""
        return await invoke(library_creates.open_output, planId, planDigest, backend="capture_dbo",
                            coverage=("verified_created_library_snapshot",))

    @register(readonly=False)
    async def capture_plan_wire_edit(sessionId: str, wireId: str, operation: Literal["set_endpoints", "delete"],
                                       expectedConnections: list[PinExpectation], start: list[int] | None = None,
                                       end: list[int] | None = None, aliasLocations: list[WireAliasLocation] | None = None,
                                       removeAttachedAliases: bool = False,
                                       expectedWirePaths: list[list[list[int]]] | None = None, expectedWireNet: str | None = None, guiSessionId: str | None = None, hostProject: str | None = None, editorOccurrence: str | None = None) -> ToolResult:
        """Plan a two-point scalar wire endpoint edit or deletion on a new DSN. Declare every page pin's result. Endpoint changes require every attached alias's saved anchor; deletion of attached aliases needs explicit acknowledgement. Match native target by unique page/old geometry/net, not an ordinal. For deletion only, paired guiSessionId/hostProject select the fixed native selection/Delete backend; provide editorOccurrence for a repeated schematic. Untouched different-net wires are frozen and checked after deletion. No junction/occurrence/DRC verdict."""
        return await invoke(wire_edits.plan, sessionId, wireId, operation,
                            [r.model_dump() for r in expectedConnections], start, end,
                            None if aliasLocations is None else [r.model_dump() for r in aliasLocations],
                            removeAttachedAliases, expectedWirePaths, expectedWireNet, guiSessionId, hostProject, editorOccurrence,
                            coverage=("wire_edit_plan", "explicit_alias_effects", "explicit_page_pin_expectations"),
                            not_checked=("save_reopen", "junction_semantics", "occurrence_connectivity", "native_drc"))

    @register(readonly=False)
    async def capture_apply_wire_edit(planId: str, planDigest: str,
                                       idempotencyKey: Annotated[str, Field(min_length=1, max_length=128)]) -> ToolResult:
        """Edit/delete one planned scalar wire, save a new DSN and independently verify full definition pin nets and connection-object geometry/aliases. Failed writes are never replayed, and source is unchanged."""
        return await invoke(wire_edits.apply, planId, planDigest, idempotencyKey, backend="capture_native",
                            coverage=("wire_edit_save_reopen", "explicit_definition_and_geometry_verification"),
                            not_checked=("junction_flags", "occurrence_connectivity", "wire_only_net_identity", "native_drc"))

    @register(readonly=True)
    async def capture_wire_edit_jobs(offset: Annotated[int, Field(ge=0, le=4096)] = 0,
                                       limit: Annotated[int, Field(ge=1, le=100)] = 100) -> ToolResult:
        """Page durable wire endpoint/delete jobs; no mutation replay."""
        return await invoke(wire_edits.jobs, offset, limit, coverage=("durable_wire_edit_jobs",))

    @register(readonly=False)
    async def capture_cancel_wire_edit(planId: str, planDigest: str) -> ToolResult:
        """Cancel pending plans or signal this server's active standalone worker. Editor-host tasks are pending-only; never kill Capture or a forwarder to cancel a started task."""
        return await invoke(wire_edits.cancel, planId, planDigest, coverage=("owned_wire_edit_cancel",))

    @register(readonly=False)
    async def capture_recover_wire_edit(planId: str, planDigest: str) -> ToolResult:
        """Verify existing interrupted wire-edit output after proof original worker stopped. No replay or native-completion claim."""
        return await invoke(wire_edits.recover, planId, planDigest, backend="capture_native",
                            coverage=("existing_wire_edit_artifact_verification",), not_checked=("native_completion", "junction_semantics", "native_drc"))

    @register(readonly=False)
    async def capture_plan_wire_add(sessionId: str, pageId: str, start: list[int], end: list[int], netName: str,
                                     expectedConnections: list[PinExpectation], aliasLocation: list[int] | None = None,
                                     expectedWirePaths: list[list[list[int]]] | None = None, expectedWireNet: str | None = None,
                                     guiSessionId: str | None = None, hostProject: str | None = None, editorOccurrence: str | None = None) -> ToolResult:
        """Plan one scalar segment plus an on-wire alias in a new DSN. Require explicit expectations for every page pin. Expected saved paths may declare splits/merges but must preserve the exact old-plus-new geometric union. Defaults keep each old path and add one segment. Expected alias-owner native net defaults to netName, or supply expectedWireNet when an existing canonical name must prevail. Provide both guiSessionId and hostProject to use fixed native OPage/PlaceWire/PlaceNetAlias in the output PCB project; the clean control host is restored and old GUI sessions invalidated. For a repeated schematic provide its unique editorOccurrence reference. The native occurrence map rejects ambiguity before OPage, and output closure requires the native DSN lock to disappear. Editor cancellation is pending-only; uncertain dispatch retains its host fence. Omit both for the existing standalone Dbo backend. No implicit electrical/DRC inference."""
        return await invoke(wire_adds.plan, sessionId, pageId, start, end, netName,
                            [row.model_dump() for row in expectedConnections], aliasLocation, expectedWirePaths, expectedWireNet, guiSessionId, hostProject, editorOccurrence,
                            coverage=("wire_alias_plan", "explicit_page_pin_expectations", "geometry_union_preflight"),
                            not_checked=("save_reopen", "junction_semantics", "occurrence_connectivity", "native_drc"))

    @register(readonly=False)
    async def capture_apply_wire_add(planId: str, planDigest: str,
                                      idempotencyKey: Annotated[str, Field(min_length=1, max_length=128)]) -> ToolResult:
        """Create the planned wire/alias in a new output, save, independently reopen and verify all definition pin nets, declared wire paths/aliases and other connection objects. Source unchanged; never replay a started job. Does not verify occurrence or wire-only net identity."""
        return await invoke(wire_adds.apply, planId, planDigest, idempotencyKey, backend="capture_native",
                            coverage=("wire_alias_save_reopen", "explicit_definition_expectations", "connection_object_preservation"),
                            not_checked=("occurrence_connectivity", "wire_only_net_identity", "native_drc", "rendered_layout"))

    @register(readonly=True)
    async def capture_wire_add_jobs(offset: Annotated[int, Field(ge=0, le=4096)] = 0,
                                      limit: Annotated[int, Field(ge=1, le=100)] = 100) -> ToolResult:
        """Page durable wire-add plans/jobs, including after server restart. No mutation replay."""
        return await invoke(wire_adds.jobs, offset, limit, coverage=("durable_wire_add_jobs",))

    @register(readonly=False)
    async def capture_cancel_wire_add(planId: str, planDigest: str) -> ToolResult:
        """Cancel a pending wire plan or signal this server's owned standalone worker. Editor-host tasks are pending-only; retain evidence and never kill Capture."""
        return await invoke(wire_adds.cancel, planId, planDigest, coverage=("owned_wire_add_cancel",))

    @register(readonly=False)
    async def capture_recover_wire_add(planId: str, planDigest: str) -> ToolResult:
        """Verify an existing interrupted wire output only after its original worker is proven stopped. Never replay mutation; no native completion claim after recovery."""
        return await invoke(wire_adds.recover, planId, planDigest, backend="capture_native",
                            coverage=("existing_wire_artifact_verification",), not_checked=("native_completion", "occurrence_connectivity", "native_drc"))

    @register(readonly=False)
    async def capture_plan_user_property(sessionId: str, partId: str, operation: Literal["set", "delete"],
                                          propertyName: Annotated[str, Field(min_length=1, max_length=64)],
                                          value: Annotated[str, Field(max_length=1024)] | None = None,
                                          expectedEffectiveAfterDelete: Annotated[str, Field(max_length=1024)] | None = None) -> ToolResult:
        """Plan explicit user-metadata creation/update/deletion on an unambiguous part in a new copy. Set requires value (empty is retained); delete requires an existing user property and an exact effective fallback expectation (null means absent). Native identity/model/source fields are protected."""
        return await invoke(user_properties.plan, sessionId, partId, operation, propertyName, value, expectedEffectiveAfterDelete,
                            coverage=("explicit_user_property_plan",), not_checked=("save_reopen", "full_inheritance_chain"))

    @register(readonly=False)
    async def capture_apply_user_property(planId: str, planDigest: str,
                                           idempotencyKey: Annotated[str, Field(min_length=1, max_length=128)]) -> ToolResult:
        """Apply a user-property plan to a new DSN, save and independently verify explicit/user effective results, unrelated user properties and definition pin nets. Never edits the source or replays a started job."""
        return await invoke(user_properties.apply, planId, planDigest, idempotencyKey, backend="capture_dbo",
                            coverage=("user_property_save_reopen", "explicit_effective_result", "definition_baseline_preservation"),
                            not_checked=("display_property_editing", "occurrence_connectivity", "electrical_behavior", "native_drc"))

    @register(readonly=True)
    async def capture_user_property_jobs(offset: Annotated[int, Field(ge=0, le=4096)] = 0,
                                          limit: Annotated[int, Field(ge=1, le=100)] = 100) -> ToolResult:
        """Page durable user-property plans/jobs in this host workspace, including after server restart; never replay."""
        return await invoke(user_properties.jobs, offset, limit, coverage=("durable_user_property_jobs",))

    @register(readonly=False)
    async def capture_cancel_user_property(planId: str, planDigest: str) -> ToolResult:
        """Cancel a pending user-property plan or signal this server's active owned worker. Query durable jobs for final state; no source change or rollback."""
        return await invoke(user_properties.cancel, planId, planDigest, coverage=("owned_user_property_cancel",))

    @register(readonly=False)
    async def capture_recover_user_property(planId: str, planDigest: str) -> ToolResult:
        """Only verify an existing interrupted user-property output after proof its worker stopped; no replay. Native completion remains unverified after recovery."""
        return await invoke(user_properties.recover, planId, planDigest, backend="capture_dbo",
                            coverage=("existing_user_property_artifact_verification",), not_checked=("native_completion", "electrical_behavior"))

    @register(readonly=False)
    async def capture_open_edit_result(planId: str, planDigest: str, kind: Literal["property", "cache_replace", "user_property", "display_property", "display_font", "wire_add", "wire_edit", "bus_create", "placement", "multiunit_placement", "graphic_line", "graphic_text", "part_edit", "design_create", "reference", "hierarchy_clone", "nc", "alias", "net_symbol_create", "net_symbol_edit"]) -> ToolResult:
        """Open a verified isolated edit output as a fresh immutable session for chained operations, including after server restart. No arbitrary path/root expansion; reject unverified or changed artifacts."""
        writer = {"property": property_edits, "cache_replace": cache_replacements, "user_property": user_properties, "display_property": display_properties, "display_font": display_fonts, "wire_add": wire_adds, "wire_edit": wire_edits, "bus_create": bus_creates, "placement": placements, "multiunit_placement": multiunit_placements, "graphic_line": graphic_lines, "graphic_text": graphic_texts, "part_edit": part_edits, "design_create": design_creates, "reference": reference_edits, "hierarchy_clone": hierarchy_edits, "nc": nc_edits, "alias": alias_edits, "net_symbol_edit": net_symbol_edits, "net_symbol_create": net_symbol_creates}[kind]
        return await invoke(writer.open_output, planId, planDigest, backend="capture_dbo",
                            coverage=("verified_output_session",), not_checked=("external_dependencies", "occurrence_connectivity"))

    @register(readonly=False)
    async def capture_plan_hierarchy_clone(sessionId: str, partId: str,
            newReference: Annotated[str, Field(min_length=1, max_length=64)], location: list[int],
            expectedPins: list[PartHotSpot]) -> ToolResult:
        """Plan same-page reuse of a resolved top-level internal block; new boundary pins must remain unbound. Explicit hotspots required. External and nested sources unsupported."""
        return await invoke(hierarchy_edits.plan, sessionId, partId, newReference, location,
                            [p.model_dump() for p in expectedPins], coverage=("internal_block_reuse_plan", "native_partition_baseline"))

    @register(readonly=False)
    async def capture_apply_hierarchy_clone(planId: str, planDigest: str,
            idempotencyKey: Annotated[str, Field(min_length=1, max_length=128)]) -> ToolResult:
        """Reuse an internal block in a new DSN, save/reopen and verify declared geometry, definitions, tree, original occurrence properties and native flat partitions. Never replay started work."""
        return await invoke(hierarchy_edits.apply, planId, planDigest, idempotencyKey, backend="capture_dbo",
                            coverage=("internal_block_save_reopen", "native_private_partition_isolation"),
                            not_checked=("port_crud", "new_definition", "annotation", "native_drc"))

    @register(readonly=True)
    async def capture_hierarchy_clone_jobs(offset: Annotated[int, Field(ge=0, le=4096)] = 0,
            limit: Annotated[int, Field(ge=1, le=100)] = 100) -> ToolResult:
        """Page durable hierarchy reuse jobs without replay."""
        return await invoke(hierarchy_edits.jobs, offset, limit, coverage=("durable_hierarchy_jobs",))

    @register(readonly=False)
    async def capture_cancel_hierarchy_clone(planId: str, planDigest: str) -> ToolResult:
        """Cancel a pending or this server's active owned hierarchy reuse worker; retain partial artifacts."""
        return await invoke(hierarchy_edits.cancel, planId, planDigest, coverage=("owned_hierarchy_cancel",))

    @register(readonly=False)
    async def capture_recover_hierarchy_clone(planId: str, planDigest: str) -> ToolResult:
        """Verify existing stopped hierarchy output only; never repeat native mutation or claim recovered native completion."""
        return await invoke(hierarchy_edits.recover, planId, planDigest, backend="capture_dbo",
                            coverage=("existing_hierarchy_output_verification",), not_checked=("native_completion",))

    @register(readonly=False)
    async def capture_plan_nc_edit(sessionId: str, pinId: str, enabled: bool) -> ToolResult:
        """Plan NC add/remove on one unbound scalar pin of an internal single-unit placed part. Bind immutable source, pin identity, old flag and hotspot; no source edits."""
        return await invoke(nc_edits.plan, sessionId, pinId, enabled, coverage=("scalar_nc_plan", "pin_identity_and_old_state"))

    @register(readonly=False)
    async def capture_apply_nc_edit(planId: str, planDigest: str,
            idempotencyKey: Annotated[str, Field(min_length=1, max_length=128)]) -> ToolResult:
        """Apply NC state on a new output and independently verify full definitions, connection objects and affected-page geometry. Never replay started work."""
        return await invoke(nc_edits.apply, planId, planDigest, idempotencyKey, backend="capture_dbo", coverage=("nc_save_reopen", "pin_and_connection_invariants"), not_checked=("bus_nc", "occurrence_connectivity", "native_drc"))

    @register(readonly=True)
    async def capture_nc_edit_jobs(offset: Annotated[int, Field(ge=0, le=4096)] = 0,
            limit: Annotated[int, Field(ge=1, le=100)] = 100) -> ToolResult:
        """Page durable NC edit jobs without mutation replay."""
        return await invoke(nc_edits.jobs, offset, limit, coverage=("durable_nc_jobs",))

    @register(readonly=False)
    async def capture_cancel_nc_edit(planId: str, planDigest: str) -> ToolResult:
        """Cancel pending or this server's active owned NC worker; keep partial evidence."""
        return await invoke(nc_edits.cancel, planId, planDigest, coverage=("owned_nc_cancel",))

    @register(readonly=False)
    async def capture_recover_nc_edit(planId: str, planDigest: str) -> ToolResult:
        """Verify an existing stopped NC output without reapplying a flag; native completion stays unproven on recovery."""
        return await invoke(nc_edits.recover, planId, planDigest, backend="capture_dbo", coverage=("existing_nc_verification",))

    @register(readonly=False)
    async def capture_plan_net_symbol_edit(sessionId: str, symbolId: str, wireId: str,
            operation: Literal["set_name", "delete"], name: str | None = None,
            expectedWireNet: str | None = None) -> ToolResult:
        """Plan scalar attached global/offpage rename/delete on a new copy. Declare native owning wire; preserve full page pin/wire memberships and unrelated names. Optional explicit saved wire name oracle; deletion otherwise permits auto naming. Pose and cross-page flat connectivity remain unverified."""
        return await invoke(net_symbol_edits.plan, sessionId, symbolId, wireId, operation, name, expectedWireNet,
                            backend="capture_dbo", coverage=("net_symbol_name_delete_plan", "native_page_partition"),
                            not_checked=("cross_page_flat_connectivity", "symbol_pose", "native_drc"))

    @register(readonly=False)
    async def capture_apply_net_symbol_edit(planId: str, planDigest: str,
            idempotencyKey: Annotated[str, Field(min_length=1, max_length=128)]) -> ToolResult:
        """Edit one scalar net symbol on an isolated output and independently verify object semantics, part geometry and native page net memberships; never replay started work."""
        return await invoke(net_symbol_edits.apply, planId, planDigest, idempotencyKey, backend="capture_dbo", coverage=("net_symbol_save_reopen", "native_page_membership_invariants"), not_checked=("occurrence_flat_nets", "global_cross_page_connectivity", "native_drc"))

    @register(readonly=True)
    async def capture_net_symbol_edit_jobs(offset: Annotated[int, Field(ge=0, le=4096)] = 0,
            limit: Annotated[int, Field(ge=1, le=100)] = 100) -> ToolResult:
        """Page durable scalar net symbol jobs without replay."""
        return await invoke(net_symbol_edits.jobs, offset, limit, coverage=("durable_net_symbol_jobs",))

    @register(readonly=False)
    async def capture_cancel_net_symbol_edit(planId: str, planDigest: str) -> ToolResult:
        """Cancel a pending or this server's active owned net symbol edit worker; retain uncertain output."""
        return await invoke(net_symbol_edits.cancel, planId, planDigest, coverage=("owned_net_symbol_cancel",))

    @register(readonly=False)
    async def capture_recover_net_symbol_edit(planId: str, planDigest: str) -> ToolResult:
        """Verify existing stopped net symbol output without repeating mutation or claiming recovered native completion."""
        return await invoke(net_symbol_edits.recover, planId, planDigest, backend="capture_dbo", coverage=("existing_net_symbol_verification",))

    @register(readonly=False)
    async def capture_plan_alias_edit(sessionId: str, aliasId: str, operation: Literal["set", "delete"],
            name: str | None = None, location: list[int] | None = None, expectedWireNet: str | None = None) -> ToolResult:
        """Plan standalone scalar alias name/anchor edit or deletion. Preserve native page pin/wire memberships; no intentional net merges. Deletion may generate a new native net name without changing connections."""
        return await invoke(alias_edits.plan, sessionId, aliasId, operation, name, location, expectedWireNet, coverage=("scalar_alias_plan", "native_page_membership_baseline"))

    @register(readonly=False)
    async def capture_apply_alias_edit(planId: str, planDigest: str,
            idempotencyKey: Annotated[str, Field(min_length=1, max_length=128)]) -> ToolResult:
        """Edit one scalar alias on an isolated output and independently verify object semantics, part geometry and native page net memberships; never replay started work."""
        return await invoke(alias_edits.apply, planId, planDigest, idempotencyKey, backend="capture_dbo", coverage=("alias_save_reopen", "native_page_membership_invariants"), not_checked=("occurrence_flat_nets", "global_cross_page_connectivity", "native_drc"))

    @register(readonly=True)
    async def capture_alias_edit_jobs(offset: Annotated[int, Field(ge=0, le=4096)] = 0,
            limit: Annotated[int, Field(ge=1, le=100)] = 100) -> ToolResult:
        """Page durable scalar alias jobs without replay."""
        return await invoke(alias_edits.jobs, offset, limit, coverage=("durable_alias_jobs",))

    @register(readonly=False)
    async def capture_cancel_alias_edit(planId: str, planDigest: str) -> ToolResult:
        """Cancel a pending or this server's active owned alias edit worker; retain uncertain output."""
        return await invoke(alias_edits.cancel, planId, planDigest, coverage=("owned_alias_cancel",))

    @register(readonly=False)
    async def capture_recover_alias_edit(planId: str, planDigest: str) -> ToolResult:
        """Verify existing stopped alias output without repeating mutation or claiming recovered native completion."""
        return await invoke(alias_edits.recover, planId, planDigest, backend="capture_dbo", coverage=("existing_alias_verification",))

    @register(readonly=False)
    async def capture_plan_net_symbol_create(sessionId: str, pageId: str, libraryId: str, symbolId: str,
            name: str, location: list[int], expectedHotSpot: list[int], expectedConnections: list[PinExpectation],
            rotationCode: Annotated[int, Field(ge=0, le=3)] = 0, mirrorCode: Annotated[int, Field(ge=0, le=1)] = 0,
            leadEnd: list[int] | None = None) -> ToolResult:
        """Plan source-bound global/offpage glyph creation with explicit origin/hotspot and every page pin expectation. Optional orthogonal lead must end at one unbound internal single-unit pin. No cross-page/global-flat verdict."""
        return await invoke(net_symbol_creates.plan, sessionId, pageId, libraryId, symbolId, name, location, expectedHotSpot,
                            [r.model_dump() for r in expectedConnections], rotationCode, mirrorCode, leadEnd,
                            coverage=("source_bound_net_symbol_plan", "explicit_hotspot_pin_oracles"))

    @register(readonly=False)
    async def capture_apply_net_symbol_create(planId: str, planDigest: str,
            idempotencyKey: Annotated[str, Field(min_length=1, max_length=128)]) -> ToolResult:
        """Create copied net symbol/optional lead on a fresh DSN; independently verify full definitions, objects, page geometry and selected native symbol/wire/pin binding. Never replay started work."""
        return await invoke(net_symbol_creates.apply, planId, planDigest, idempotencyKey, backend="capture_dbo", coverage=("net_symbol_save_reopen", "selected_native_page_binding"), not_checked=("global_cross_page_flat_connectivity", "native_drc"))

    @register(readonly=True)
    async def capture_net_symbol_create_jobs(offset: Annotated[int, Field(ge=0, le=4096)] = 0,
            limit: Annotated[int, Field(ge=1, le=100)] = 100) -> ToolResult:
        """Page durable source-bound net-symbol jobs without replay."""
        return await invoke(net_symbol_creates.jobs, offset, limit, coverage=("durable_net_symbol_jobs",))

    @register(readonly=False)
    async def capture_cancel_net_symbol_create(planId: str, planDigest: str) -> ToolResult:
        """Cancel a pending or this server's active owned net-symbol worker; retain partial output."""
        return await invoke(net_symbol_creates.cancel, planId, planDigest, coverage=("owned_net_symbol_cancel",))

    @register(readonly=False)
    async def capture_recover_net_symbol_create(planId: str, planDigest: str) -> ToolResult:
        """Verify existing stopped net-symbol output and source hashes, never recreate the symbol or claim recovered native completion."""
        return await invoke(net_symbol_creates.recover, planId, planDigest, backend="capture_dbo", coverage=("existing_net_symbol_verification",))

    @register(readonly=False)
    async def capture_plan_property(sessionId: str, partId: str, propertyName: Literal["Value", "PCB Footprint", "Implementation", "TC1", "TC2"],
                                     value: Annotated[str, Field(max_length=1024)]) -> ToolResult:
        """Plan one existing approved Value/PCB Footprint/Implementation/TC1/TC2 change on an unambiguous part definition. Implementation requires an existing PSpice Model type. Model identifiers and finite decimal coefficients are bounded; new plans also freeze the complete effective-property multiset. Model existence and simulation behavior require separate validation. Apply always creates a new isolated DSN; never edits the source or a GUI design. Shared references/multi-unit edits require a dedicated operation."""
        return await invoke(property_edits.plan, sessionId, partId, propertyName, value,
                            coverage=("isolated_property_plan",), not_checked=("save_reopen", "electrical_behavior"))

    @register(readonly=False)
    async def capture_apply_property(planId: str, planDigest: str,
                                      idempotencyKey: Annotated[str, Field(min_length=1, max_length=128)]) -> ToolResult:
        """Apply a durable property plan to a new DSN copy, save, independently reopen and check the explicit value plus pre-change definition pin nets. Owned process tree, no replay of started jobs. New plans also verify the complete effective-property multiset. Does not resolve external model definitions or validate electrical behavior/DRC/occurrence nets."""
        return await invoke(property_edits.apply, planId, planDigest, idempotencyKey, backend="capture_dbo",
                            coverage=("isolated_property_save_reopen", "definition_baseline_preservation"),
                            not_checked=("electrical_behavior", "native_drc", "occurrence_connectivity"))

    @register(readonly=True)
    async def capture_property_jobs(offset: Annotated[int, Field(ge=0, le=4096)] = 0,
                                     limit: Annotated[int, Field(ge=1, le=100)] = 100) -> ToolResult:
        """Page durable isolated property jobs after server restart; read statuses without replay. New jobs can change listing order while paging."""
        return await invoke(property_edits.jobs, offset, limit, coverage=("durable_isolated_property_jobs",))

    @register(readonly=False)
    async def capture_cancel_property(planId: str, planDigest: str) -> ToolResult:
        """Cancel a pending isolated plan, or signal this server's active owned process tree. Source is never modified; retain partial output. Query jobs for final cancellation state; no rollback/replay."""
        return await invoke(property_edits.cancel, planId, planDigest, coverage=("isolated_property_cancellation",))

    @register(readonly=False)
    async def capture_recover_property(planId: str, planDigest: str) -> ToolResult:
        """Verify an existing failed/interrupted output only after proof its worker stopped. Never reapply. Recovery may verify the artifact while nativeCompletionVerified remains false."""
        return await invoke(property_edits.recover, planId, planDigest, backend="capture_dbo",
                            coverage=("existing_isolated_artifact_verification",), not_checked=("native_completion", "electrical_behavior"))

    @register(readonly=False)
    async def capture_get_property_layers(sessionId: str, partId: str) -> ToolResult:
        """Read effective values, explicit user properties and display-property values/owner-local positions separately. Does not infer a full library/cache/occurrence inheritance chain or editability."""
        return await invoke(read_property_layers, capture, sessionId, partId, backend="capture_dbo",
                            coverage=("effective_user_display_property_layers",),
                            not_checked=("full_inheritance_chain", "occurrence_properties", "rendered_text_bounds", "property_write"))

    @register(readonly=False)
    async def capture_get_part_properties(sessionId: str, partId: str) -> ToolResult:
        """Read up to 512 effective properties of one revision-bound part definition in a fresh Dbo worker. Use partId from capture_query; includes inherited effective values without asserting their origin or editability. No GUI or mutation."""
        return await invoke(read_part_properties, capture, sessionId, partId, backend="capture_dbo",
                            coverage=("part_definition_effective_properties",),
                            not_checked=("property_origin", "editability", "occurrence_properties", "property_write"))

    @register(readonly=False)
    async def capture_snapshot(sessionId: str) -> ToolResult:
        """Write an immutable JSON snapshot artifact in its registered workspace; it is not an independently verified connectivity baseline."""
        return await invoke(capture.snapshot, sessionId, backend="capture_dbo", coverage=("design_definitions",),
                            not_checked=("occurrence_connectivity", "independent_expected_connectivity"))

    @register(readonly=False)
    async def capture_check_wiring(sessionId: str,
                                   gridSize: Annotated[int, Field(ge=1, le=1000000)] | None = None,
                                   gridOrigin: list[int] | None = None) -> ToolResult:
        """Read wire polylines in a fresh standalone worker and write an exact linear geometry advisory, including diagonal crossings/overlaps. Non-integer crossings use pointExact rational coordinates. Optional gridSize/gridOrigin check vertices in native units; absent grid means no grid verdict. No GUI/PDF, junction or electrical verdict. Limited to 2000 segments/10000 vertices/findings."""
        return await invoke(capture.check_wiring, sessionId, gridSize, gridOrigin, backend="capture_dbo",
                            coverage=("wire_coordinates", "exact_linear_geometry_candidates", "explicit_grid_when_requested"),
                            not_checked=("junction_semantics", "occurrence_connectivity", "native_drc", "symbol_text_clearance"))

    @register(readonly=False)
    async def capture_compare_connections(
        sessionId: str,
        expectedRevision: Annotated[str, Field(pattern="^[a-f0-9]{64}$")],
        expectations: Annotated[list[PinExpectation], Field(min_length=1, max_length=10000)],
        expectationSource: Annotated[str, Field(min_length=1, max_length=1024)],
    ) -> ToolResult:
        """Compare explicit named pin expectations against a revision-bound immutable Dbo snapshot and write a report. Exact names only; ambiguous definitions stay unverified. No occurrence/net-equivalence/DRC verdict; never generate expectations from observations."""
        return await invoke(capture.compare_connections, sessionId, expectedRevision,
                            [row.model_dump() for row in expectations], expectationSource,
                            backend="capture_dbo_snapshot", coverage=("selected_expected_pin_observations",),
                            not_checked=("unlisted_pins", "net_equivalence", "occurrence_connectivity", "native_drc",
                                         "expectation_source_independence"))

    @register(readonly=False)
    async def capture_close(sessionId: str) -> ToolResult:
        """Release this server's cached read-only session; never save, delete a design, or touch a Capture GUI session."""
        return await invoke(capture.close, sessionId, coverage=("cache_release",))

    if profile=='validated' and {tool.name for tool in tools}!=VALIDATED_TOOLS:raise ValueError('Validated release registration differs from its whitelist')
    return MCPServer("cadence-mcp", version=__version__, tools=tools, log_level="WARNING", lifespan=lifespan,
                     instructions="Work only in registered copies. GUI sessions default to read access. Experimental fixed MCP_NOTE writes require a prepared fixture binding and immutable plan; uncertain writes are never replayed. Definition-level pin nets are not occurrence-expanded connectivity. Approved isolated property edits require a durable plan and produce a new copy. Only capabilities listed by cadence_get_capabilities are supported. Full schematic authoring, native DRC, PDF delivery and end-to-end Capture-to-PSpice remain incomplete.")


def parse_config(argv: list[str] | None = None) -> Config:
    parser = argparse.ArgumentParser(description="Local Cadence MCP server with immutable queries and isolated planned writes")
    parser.add_argument("--install-root", required=True, type=Path)
    parser.add_argument("--workspace-root", required=True, type=Path)
    parser.add_argument("--read-root", required=True, action="append", type=Path)
    parser.add_argument("--timeout-seconds", default=30, type=int)
    parser.add_argument("--gui-bridge-config", type=Path)
    parser.add_argument("--gui-bridge-root", action="append", type=Path, default=[])
    args = parser.parse_args(argv)
    return Config(args.install_root, args.workspace_root, tuple(args.read_root), args.timeout_seconds, args.gui_bridge_config, tuple(args.gui_bridge_root))


def main() -> None:
    create_server(parse_config()).run(transport="stdio")


if __name__ == "__main__":
    main()



