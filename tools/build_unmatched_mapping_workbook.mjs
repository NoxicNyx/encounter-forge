import fs from "node:fs/promises";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const projectRoot = process.cwd();
const outputDir = path.join(projectRoot, "outputs", "unmatched-creature-mapping");
const databasePath = path.join(projectRoot, "db", "encounter_forge.db");
const pythonPath = "C:\\Users\\Thomas\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe";

const queryScript = `
import json
import sqlite3
import sys

con = sqlite3.connect(sys.argv[1])
profiles = [row[0] for row in con.execute("""
    SELECT tp.source_name
    FROM tactical_profiles AS tp
    LEFT JOIN tactical_profile_monster_links AS l ON l.tactical_profile_id = tp.id
    GROUP BY tp.id, tp.source_name
    HAVING COUNT(l.monster_id) = 0
    ORDER BY tp.source_name COLLATE NOCASE
""")]
creatures = [row[0] for row in con.execute("""
    SELECT m.name
    FROM monsters AS m
    JOIN sources AS s ON s.id = m.source_id
    LEFT JOIN tactical_profile_monster_links AS l ON l.monster_id = m.id
    WHERE s.source_key = 'srd-2024'
    GROUP BY m.id, m.name
    HAVING COUNT(l.tactical_profile_id) = 0
    ORDER BY m.name COLLATE NOCASE
""")]
print(json.dumps({"profiles": profiles, "creatures": creatures}, ensure_ascii=False))
`;

const queryResult = spawnSync(pythonPath, ["-c", queryScript, databasePath], {
  cwd: projectRoot,
  encoding: "utf8",
});
if (queryResult.status !== 0) {
  throw new Error(queryResult.stderr || "Unable to query the encounter database.");
}
const { profiles, creatures } = JSON.parse(queryResult.stdout);

const workbook = Workbook.create();

function makeMappingSheet({ sheetName, title, sourceHeader, targetHeader, sourceItems, tableName }) {
  const sheet = workbook.worksheets.add(sheetName);
  sheet.showGridLines = false;

  sheet.getRange("A1:C1").values = [[title, "", ""]];
  sheet.getRange("A2:C2").values = [[
    "Enter a deliberate connection in the amber column. Leave it blank when there is no valid pairing; use Notes for category-level or uncertain cases.",
    "",
    "",
  ]];
  sheet.getRange("A4:C4").values = [[sourceHeader, targetHeader, "Notes"]];
  sheet.getRange(`A5:C${sourceItems.length + 4}`).values = sourceItems.map((item) => [
    item,
    "",
    item === "Doppelg�nger" ? "Workbook text appears malformed; likely Doppelganger." : "",
  ]);

  const usedRange = sheet.getRange(`A1:C${sourceItems.length + 4}`);
  usedRange.format.font = { name: "Arial", size: 10, color: "#211A17" };
  usedRange.format.verticalAlignment = "center";
  usedRange.format.wrapText = false;

  sheet.getRange("A1:C1").format.font = { name: "Arial", size: 14, bold: true, color: "#211A17" };
  sheet.getRange("A2:C2").format.font = { name: "Arial", size: 10, italic: true, color: "#5F5148" };
  sheet.getRange("A4:C4").format = {
    fill: "#4A2C1D",
    font: { name: "Arial", size: 10, bold: true, color: "#FFFFFF" },
    horizontalAlignment: "center",
    verticalAlignment: "center",
    borders: { preset: "inside", style: "thin", color: "#FFFFFF" },
  };
  sheet.getRange(`A4:C${sourceItems.length + 4}`).format.borders = {
    preset: "outside",
    style: "thin",
    color: "#B7A89B",
  };
  sheet.getRange(`B5:C${sourceItems.length + 4}`).format.fill = "#FFF2CC";

  sheet.getRange("A:A").format.columnWidth = 34;
  sheet.getRange("B:B").format.columnWidth = 38;
  sheet.getRange("C:C").format.columnWidth = 46;
  sheet.getRange("A1:C1").format.rowHeight = 24;
  sheet.getRange("A2:C2").format.rowHeight = 20;
  sheet.getRange("A4:C4").format.rowHeight = 22;
  sheet.freezePanes.freezeRows(4);
  sheet.tables.add(`A4:C${sourceItems.length + 4}`, true, tableName);
  sheet.tabColor = "#6A3F26";
}

makeMappingSheet({
  sheetName: "Profiles to 2024",
  title: `Unmatched tactical profiles (${profiles.length})`,
  sourceHeader: "Tactical profile without a 2024 match",
  targetHeader: "Pair with 2024 creature",
  sourceItems: profiles,
  tableName: "UnmatchedProfilesTable",
});

makeMappingSheet({
  sheetName: "2024 to Profiles",
  title: `Unmatched 2024 creatures (${creatures.length})`,
  sourceHeader: "2024 creature without a tactical profile",
  targetHeader: "Pair with tactical profile",
  sourceItems: creatures,
  tableName: "Unmatched2024CreaturesTable",
});

workbook.recalculate();
await fs.mkdir(outputDir, { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(path.join(outputDir, "Encounter_Forge_Unmatched_Creature_Mapping.xlsx"));

const profileCheck = await workbook.inspect({
  kind: "table",
  range: "Profiles to 2024!A1:C12",
  include: "values,formulas",
  tableMaxRows: 12,
  tableMaxCols: 3,
});
const creatureCheck = await workbook.inspect({
  kind: "table",
  range: "2024 to Profiles!A1:C12",
  include: "values,formulas",
  tableMaxRows: 12,
  tableMaxCols: 3,
});
const formulaErrors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",
  options: { useRegex: true, maxResults: 100 },
  summary: "formula error scan",
});
const preview = await workbook.render({
  sheetName: "Profiles to 2024",
  range: "A1:C16",
  scale: 2,
  format: "png",
});
await fs.writeFile(path.join(outputDir, "mapping-preview.png"), new Uint8Array(await preview.arrayBuffer()));

console.log(JSON.stringify({
  profiles: profiles.length,
  creatures: creatures.length,
  profileCheck: profileCheck.ndjson,
  creatureCheck: creatureCheck.ndjson,
  formulaErrors: formulaErrors.ndjson,
}, null, 2));
