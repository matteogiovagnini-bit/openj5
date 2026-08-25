#!/bin/sh
# OpenJ5 documentation gate: verifies mandatory documents exist and
# that every ADR referenced by docs/adr/INDEX.md resolves to a file.
set -e

cd "$(dirname "$0")/.."

status=0

for f in \
    README.md \
    CHANGELOG.md \
    ROADMAP.md \
    PROJECT_STATUS.md \
    Development_Constitution.md \
    PERSISTENT_PROJECT_MEMORY.md \
    MASTER_PROMPT.md \
    governance/VISION.md \
    governance/MISSION.md \
    governance/GOALS.md \
    governance/NON_GOALS.md \
    governance/CONSTRAINTS.md \
    governance/ARCHITECTURAL_PRINCIPLES.md \
    governance/CODING_STANDARD.md \
    governance/NAMING_CONVENTIONS.md \
    docs/architecture/ARCHITECTURE.md \
    docs/api/API.md \
    docs/configuration/CONFIGURATION.md \
    docs/adr/INDEX.md \
    docs/adr/TEMPLATE.md \
    docs/PROJECT_MEMORY.md \
    docs/NEXT_TASK.md \
    docs/KNOWLEDGE_BASE.md \
    docs/CONTINUATION_PROMPT.md; do
    if [ ! -f "$f" ]; then
        echo "MISSING: $f"
        status=1
    fi
done

grep -o '](ADR-[^)]*)' docs/adr/INDEX.md | tr -d ']()' | while read -r adr; do
    if [ ! -f "docs/adr/$adr" ]; then
        echo "BROKEN ADR LINK in INDEX.md: $adr"
        exit 1
    fi
done || status=1

if [ "$status" -eq 0 ]; then
    echo "doc-check OK"
fi
exit "$status"
