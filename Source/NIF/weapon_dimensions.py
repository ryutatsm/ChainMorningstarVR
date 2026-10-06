"""Read literal authoring dimensions from the runtime's shared contract."""
from pathlib import Path
import re

HEADER = Path(__file__).resolve().parents[1] / 'SKSE/WeaponDimensions.hpp'
_source = HEADER.read_text()

def literal(name):
    match = re.search(r'\b' + re.escape(name) + r' = ([0-9.]+)f?;', _source)
    if not match:
        raise ValueError(f'Missing literal dimension: {name}')
    return float(match.group(1))

MODEL_SCALE = literal('kModelScale')
LINK_COUNT = int(literal('kChainLinkCount'))
FIRST_LINK = literal('kUnscaledFirstLinkOffsetM')
LINK_SPACING = literal('kUnscaledLinkSpacingM')
LAST_LINK_HEAD = literal('kUnscaledLastLinkHeadOffsetM')
HEAD_REACH = FIRST_LINK + (LINK_COUNT - 1) * LINK_SPACING + LAST_LINK_HEAD
assert 0 < MODEL_SCALE <= 1 and 1 <= LINK_COUNT <= 64
