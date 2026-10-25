# Source from Capture after gui_probe.tcl. This is a manual native validation
# utility, not a registered MCP tool or general executable-command interface.
namespace eval ::cadenceGuiPdf {}
# Historical diagnostic only: Export output failed searchable-text acceptance.
proc ::cadenceGuiPdf::run {args} {
    error "Use Capture File > Print with a validated PDF printer; legacy Export is diagnostic-only"
}
proc ::cadenceGuiPdf::legacyDiagnosticExport {target outputDir {fileName gui-smoke.pdf}} {
    set target [file normalize $target]
    set outputDir [file normalize $outputDir]
    if {![file isfile $target] || ![string equal -nocase [file dirname $target] $outputDir]} {
        error "PDF validation requires the copied design in the output directory"
    }
    package require OrHandlerPDFExport
    set actual [::OrHandlerPDFExport::GetActiveDesignName]
    if {![string equal -nocase [file normalize $actual] $target]} {error "Wrong active PDF design"}
    if {[file tail $fileName] ne $fileName || ![string equal -nocase [file extension $fileName] .pdf]} {
        error "PDF output must be a simple PDF file name"
    }
    set output [file join $outputDir $fileName]
    if {[file exists $output]} {error "Refusing to overwrite an earlier PDF"}
    # Reuse the already configured local converter; never accept a shell command.
    set index [GetOptionString capPDFCommandIndex]
    if {$index ne "2"} {error "This validation recipe requires the existing 64-bit Ghostscript configuration"}
    set converter [GetOptionString "capPDFCommand$index"]
    if {![file isfile [lindex $converter 0]]} {error "Configured converter executable is missing"}
    if {[::OrHandlerPDFExport::checkPrinterDriver [GetOptionString capPDFDriver]] != 1} {
        error "Configured PostScript printer is missing"
    }
    set overrides {capPDFPrintingMode 1 capPDFOrientation 1 capPDFCreatePropertiesFile 0 capPDFCreateNetAndBookmark 1 capPDFPaperSize 0}
    set original {}
    foreach {key value} $overrides {dict set original $key [GetOptionString $key]}
    try {
        foreach {key value} $overrides {SetOptionString $key $value}
        if {![string equal -nocase [file normalize [::OrHandlerPDFExport::GetActiveDesignName]] $target]} {
            error "Active PDF design changed"
        }
        # Keep PS/mark files for diagnostics, and do not launch an external viewer.
        ::capPdfUtil::printPdfEx $outputDir $fileName 0 0
    } finally {
        dict for {key value} $original {SetOptionString $key $value}
    }
    puts "CADENCE_GUI_PDF_RETURNED $output"
    puts "PDF must still be checked for fresh content, page count and visual correctness."
}
