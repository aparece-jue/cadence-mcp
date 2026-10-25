# Source manually from Capture Command Window; all writes stay in outputDir.
# Usage: ::cadenceGuiProbe::run copiedDesign.dsn outputDir
# This never saves a design or deletes the Capture-owned session.
namespace eval ::cadenceGuiProbe {
    variable adapterRoot [file normalize [file join [file dirname [info script]] .. src cadence_mcp adapters]]
}
source [file join $::cadenceGuiProbe::adapterRoot json.tcl]
proc ::cadenceGuiProbe::activeDesign {} {
    set design [GetActivePMDesign]
    if {$design eq "NULL"} {return ""}
    set text [DboTclHelper_sMakeCString]
    $design GetName $text
    return [file normalize [DboTclHelper_sGetConstCharPtr $text]]
}
proc ::cadenceGuiProbe::run {target outputDir} {
    set target [file normalize $target]
    set outputDir [file normalize $outputDir]
    if {![file isfile $target] || ![string equal -nocase [file dirname $target] $outputDir]} {
        error "Probe requires a copied design directly inside its explicit output directory"
    }
    Open $target
    ::cadenceGuiProbe::record $target $outputDir
}
proc ::cadenceGuiProbe::record {target outputDir} {
    set target [file normalize $target]
    set outputDir [file normalize $outputDir]
    if {![file isfile $target] || ![string equal -nocase [file dirname $target] $outputDir]} {
        error "Probe requires a copied design directly inside its explicit output directory"
    }
    set output [file join $outputDir "gui-probe-[clock seconds].json"]
    if {[file exists $output]} {error "Probe output already exists; choose a fresh run directory"}
    set actual [::cadenceGuiProbe::activeDesign]
    if {![string equal -nocase $target $actual]} {error "Active design differs from probe target"}
    set commands {}
    foreach name {DboTclHelper_sCreateSession GetActivePMDesign GetActivePage GetSelectedObjects orExecuteDrc orExecutePst capGetDRCConfigData capSaveDRCConfigData CapPdfPrint CapPdfSetOption} {
        lappend commands $name [expr {[llength [info commands $name]] > 0 ? "true" : "false"}]
    }
    set packageVersion ""
    set packageError [catch {package require OrHandlerPDFExport} packageVersion]
    set drcConfig ""
    catch {set drcConfig [capGetDRCConfigData]}
    set pdfOptions {}
    foreach key {capPDFDriver capPDFConverter capPDFCommandIndex capPDFCommand0 capPDFCommand1 capPDFCommand2 capPDFCommand3} {
        lappend pdfOptions $key [cmcp::q [GetOptionString $key]]
    }
    set same [string equal -nocase $target $actual]
    set data [cmcp::obj timestampUtc [cmcp::q [clock format [clock seconds] -gmt true -format {%Y-%m-%dT%H:%M:%SZ}]] pid [pid] tclVersion [cmcp::q [info patchlevel]] expectedDesign [cmcp::q $target] activeDesign [cmcp::q $actual] targetMatched [expr {$same ? "true" : "false"}] commands [cmcp::obj {*}$commands] pdfPackageLoaded [expr {$packageError ? "false" : "true"}] pdfPackageResult [cmcp::q $packageVersion] pdfOptions [cmcp::obj {*}$pdfOptions] drcConfigurationRaw [cmcp::q $drcConfig] scope [cmcp::q command_visibility_only]]
    set f [open $output {WRONLY CREAT EXCL}]
    try {fconfigure $f -encoding utf-8 -translation lf; puts -nonewline $f $data} finally {close $f}
    if {!$same} {error "Active design differs from probe target; no native action was performed"}
    puts "CADENCE_GUI_PROBE_READY $output"
}
