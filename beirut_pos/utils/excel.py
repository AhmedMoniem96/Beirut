"""Minimal XLSX writer that produces read-only, password-protected workbooks.

The generated workbook locks both the workbook structure and the sheet so that
recipients cannot edit the report without the (hard-coded) password. The helper
avoids external dependencies by emitting the XML parts directly.
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Sequence
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

_PASSWORD = "POSLOCK"


def _excel_password_hash(password: str) -> str:
    """Return the legacy XOR hash Excel expects for sheet/workbook passwords."""

    trimmed = (password or "")[:15]
    if not trimmed:
        return "0000"

    hash_value = 0
    for idx, ch in enumerate(trimmed):
        hash_value = ((hash_value >> 14) & 0x01) | ((hash_value << 1) & 0x7FFF)
        hash_value ^= ord(ch)
    hash_value ^= len(trimmed)
    hash_value ^= 0xCE4B
    return f"{hash_value:04X}"


def _column_letter(index: int) -> str:
    letters = ""
    current = index
    while current >= 0:
        current, remainder = divmod(current, 26)
        letters = chr(65 + remainder) + letters
        current -= 1
    return letters


def _sanitize_sheet_name(name: str) -> str:
    invalid = set('[]:*?/\\')
    cleaned = "".join("_" if ch in invalid else ch for ch in name.strip())
    cleaned = cleaned or "Report"
    return cleaned[:31]


def write_protected_workbook(
    path: str,
    headers: Sequence[str],
    rows: Iterable[Sequence[str]],
    *,
    title: str = "Report",
    password: str = _PASSWORD,
) -> None:
    """Create a password-protected XLSX file with the given data."""

    sheet_name = _sanitize_sheet_name(title)
    timestamp = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    hashed = _excel_password_hash(password)

    header_values = [escape(str(h) if h is not None else "") for h in headers]
    table_rows = [[escape(str(cell) if cell is not None else "") for cell in row] for row in rows]

    total_rows = 1 + len(table_rows)
    total_cols = max(1, len(header_values))
    end_col_letter = _column_letter(total_cols - 1)
    dimension = f"A1:{end_col_letter}{total_rows}" if total_rows > 1 or total_cols > 1 else "A1"

    def build_row(cells: Sequence[str], row_number: int) -> str:
        parts = []
        for col_index, value in enumerate(cells):
            ref = f"{_column_letter(col_index)}{row_number}"
            parts.append(
                f'<c r="{ref}" t="inlineStr"><is><t>{value}</t></is></c>'
            )
        return f"<row r=\"{row_number}\">{''.join(parts)}</row>"

    sheet_rows = [build_row(header_values, 1)]
    for idx, data_row in enumerate(table_rows, start=2):
        sheet_rows.append(build_row(data_row, idx))

    sheet_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
           xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheetPr/>
  <dimension ref="{dimension}"/>
  <sheetViews>
    <sheetView workbookViewId="0"/>
  </sheetViews>
  <sheetFormatPr defaultRowHeight="15"/>
  <sheetProtection sheet="1" objects="1" scenarios="1" formatCells="1" formatColumns="1" formatRows="1"
                   insertColumns="1" insertRows="1" insertHyperlinks="1" deleteColumns="1" deleteRows="1"
                   selectLockedCells="1" selectUnlockedCells="1" sort="1" autoFilter="1" pivotTables="1"
                   password="{hashed}"/>
  <sheetData>
    {''.join(sheet_rows)}
  </sheetData>
  <pageMargins left="0.7" right="0.7" top="0.75" bottom="0.75" header="0.3" footer="0.3"/>
</worksheet>
"""

    workbook_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
          xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <fileVersion appName="xl" lastEdited="7" lowestEdited="7" rupBuild="22228"/>
  <workbookPr defaultThemeVersion="166925"/>
  <bookViews>
    <workbookView xWindow="0" yWindow="0" windowWidth="16384" windowHeight="8192"/>
  </bookViews>
  <sheets>
    <sheet name="{sheet_name}" sheetId="1" r:id="rId1"/>
  </sheets>
  <calcPr calcId="124519"/>
  <workbookProtection lockStructure="1" lockWindows="1" workbookPassword="{hashed}"/>
</workbook>
"""

    styles_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="1">
    <font>
      <sz val="11"/>
      <color theme="1"/>
      <name val="Calibri"/>
      <family val="2"/>
    </font>
  </fonts>
  <fills count="2">
    <fill><patternFill patternType="none"/></fill>
    <fill><patternFill patternType="gray125"/></fill>
  </fills>
  <borders count="1">
    <border>
      <left/><right/><top/><bottom/><diagonal/>
    </border>
  </borders>
  <cellStyleXfs count="1">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0"/>
  </cellStyleXfs>
  <cellXfs count="1">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyProtection="1">
      <protection locked="1"/>
    </xf>
  </cellXfs>
  <cellStyles count="1">
    <cellStyle name="Normal" xfId="0" builtinId="0"/>
  </cellStyles>
</styleSheet>
"""

    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>
"""

    rels_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>
"""

    workbook_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>
"""

    core_props = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
                   xmlns:dc="http://purl.org/dc/elements/1.1/"
                   xmlns:dcterms="http://purl.org/dc/terms/"
                   xmlns:dcmitype="http://purl.org/dc/dcmitype/"
                   xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:creator>Beirut POS</dc:creator>
  <cp:lastModifiedBy>Beirut POS</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">{timestamp}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{timestamp}</dcterms:modified>
</cp:coreProperties>
"""

    app_props = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
            xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Beirut POS</Application>
  <DocSecurity>4</DocSecurity>
  <ScaleCrop>false</ScaleCrop>
  <HeadingPairs>
    <vt:vector size="2" baseType="variant">
      <vt:variant><vt:lpstr>Worksheets</vt:lpstr></vt:variant>
      <vt:variant><vt:i4>1</vt:i4></vt:variant>
    </vt:vector>
  </HeadingPairs>
  <TitlesOfParts>
    <vt:vector size="1" baseType="lpstr">
      <vt:lpstr>{sheet_name}</vt:lpstr>
    </vt:vector>
  </TitlesOfParts>
  <Company>Beirut POS</Company>
  <LinksUpToDate>false</LinksUpToDate>
  <SharedDoc>false</SharedDoc>
  <HyperlinksChanged>false</HyperlinksChanged>
  <AppVersion>16.0300</AppVersion>
</Properties>
"""

    with ZipFile(path, "w", ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels_xml)
        zf.writestr("docProps/core.xml", core_props)
        zf.writestr("docProps/app.xml", app_props)
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        zf.writestr("xl/styles.xml", styles_xml)
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)
