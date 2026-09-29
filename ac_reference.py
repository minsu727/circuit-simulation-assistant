"""Read-only AC reference hints for standard, unrotated LTspice voltage sources.

This is not a netlist extractor. Only FLAGs and connected WIRE segments are
followed; no connection is inferred through components. Standard voltage.asy
has positive (0, 16), negative (0, 96) pins (SpiceOrder 1/2), verified against
the installed LTspice symbol. Other symbols/orientations require manual input.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re


@dataclass(frozen=True)
class ReferenceHints:
    candidates: tuple = ()
    sources: tuple = ()
    notices: tuple = ()
    ambiguous: bool = False


def _ac_state(attributes):
    """None: no excitation, False: explicit zero, True: numeric nonzero,
    'unknown': AC exists but its magnitude cannot safely be resolved locally.
    SINE/PWL parameters and comments are not AC small-signal declarations.
    """
    text = ' '.join(attributes.get(key, '') for key in ('value', 'value2', 'spiceline', 'spiceline2'))
    text = re.sub(r'\([^)]*\)', '', text)
    text = text.split(';', 1)[0]
    matches = list(re.finditer(r'(?<!\S)AC(?:\s+([^\s]+))?(?=\s|$)', text, re.I))
    if not matches:
        return None
    if len(matches) != 1:
        return 'unknown'
    magnitude = matches[0][1] or ''
    match = re.fullmatch(r'([+\-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+\-]?\d+)?)(meg|[fpnuµμmkgt])?', magnitude, re.I)
    if not match:
        return 'unknown'
    try:
        value = Decimal(match[1])
        return value != 0 if value.is_finite() else 'unknown'
    except InvalidOperation:
        return 'unknown'


def _on(point, segment):
    (x, y), ((ax, ay), (bx, by)) = point, segment
    return ((x-ax)*(by-ay) == (y-ay)*(bx-ax)
            and min(ax, bx) <= x <= max(ax, bx)
            and min(ay, by) <= y <= max(ay, by))


def _labels_at(pin, wires, flags):
    """Endpoint/T-junction connectivity only; uncertain crossings abstain."""
    reached = {i for i, wire in enumerate(wires) if _on(pin, wire)}
    pending = list(reached)
    while pending:
        i = pending.pop()
        for j, other in enumerate(wires):
            if j not in reached and (any(_on(p, other) for p in wires[i])
                                     or any(_on(p, wires[i]) for p in other)):
                reached.add(j)
                pending.append(j)
    for i in reached:
        a, b = wires[i]
        if a[0] != b[0] and a[1] != b[1]:
            return (), 'diagonal wire connectivity is not supported'
        for j, (c, d) in enumerate(wires):
            # An interior-only crossing does not establish a known junction.
            if j == i or any(_on(p, wires[j]) for p in (a, b)) or any(_on(p, wires[i]) for p in (c, d)):
                continue
            if c[0] != d[0] and c[1] != d[1]:
                # Conservative when a diagonal bounding box crosses this net.
                if max(min(a[0], b[0]), min(c[0], d[0])) <= min(max(a[0], b[0]), max(c[0], d[0])) and max(min(a[1], b[1]), min(c[1], d[1])) <= min(max(a[1], b[1]), max(c[1], d[1])):
                    return (), 'ambiguous wire crossing'
            elif (a[1] == b[1] and c[0] == d[0] and _on((c[0], a[1]), wires[i]) and _on((c[0], a[1]), wires[j])) or (a[0] == b[0] and c[1] == d[1] and _on((a[0], c[1]), wires[i]) and _on((a[0], c[1]), wires[j])):
                return (), 'ambiguous wire crossing'
    labels = sorted({name.casefold() for point, name in flags
                     if point == pin or any(_on(point, wires[i]) for i in reached)})
    return tuple(labels), ''


def suggest_ac_references(data):
    """Return candidates and uncertainty without editing bytes or invoking tools.

    A supported source needs numeric nonzero AC magnitude, standard voltage/R0,
    and a negative pin wired/labeled only to ground. Never auto-select, even for
    one candidate. Multiple sources/aliases and unsupported excitation stay visible.
    """
    try:
        text = data.decode('utf-16' if data.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig')
    except UnicodeDecodeError:
        text = data.decode('latin-1')
    if not re.match(r'\s*Version\s+\d+\b', text, re.I):
        return ReferenceHints(notices=('Cannot inspect AC references: invalid ASC header. Enter the reference manually.',), ambiguous=True)
    wires, flags, symbols = [], [], []
    current = None
    try:
        for line in text.splitlines():
            parts = line.split()
            if not parts:
                continue
            tag = parts[0].upper()
            if tag == 'WIRE':
                if len(parts) != 5:
                    raise ValueError
                x1, y1, x2, y2 = map(int, parts[1:])
                wires.append(((x1, y1), (x2, y2)))
            elif tag == 'FLAG':
                if len(parts) != 4:
                    raise ValueError
                flags.append(((int(parts[1]), int(parts[2])), parts[3]))
            elif tag == 'SYMBOL':
                if len(parts) != 5:
                    raise ValueError
                current = dict(symbol=parts[1].casefold(), x=int(parts[2]), y=int(parts[3]), orientation=parts[4].upper())
                symbols.append(current)
            elif tag == 'SYMATTR' and current is not None:
                fields = line.strip().split(None, 2)
                if len(fields) == 3:
                    key = fields[1].casefold()
                    if key in current:
                        raise ValueError  # Duplicate attributes are not silently resolved.
                    current[key] = fields[2]
            elif tag != 'WINDOW':
                current = None
        if len(wires) > 1000 or len(symbols) > 1000:
            raise ValueError
    except ValueError:
        return ReferenceHints(notices=('Cannot safely inspect ASC records or schematic size. Enter the reference manually.',), ambiguous=True)

    candidates, sources, notices = set(), [], []
    ambiguous = False
    for symbol in symbols:
        name = symbol.get('instname', '')
        if not name.upper().startswith(('V', 'I')):
            continue
        state = _ac_state(symbol)
        if state is None or state is False:
            continue
        sources.append(name)
        reason = ''
        if state == 'unknown':
            reason = 'AC magnitude is not a single numeric literal'
        elif symbol['symbol'] != 'voltage' or not name.upper().startswith('V') or symbol.get('prefix', 'V').upper() != 'V':
            reason = 'only standard independent voltage sources are supported (current/custom sources need manual review)'
        elif symbol['orientation'] != 'R0':
            reason = 'rotated/mirrored source pins are not supported'
        else:
            negative, error = _labels_at((symbol['x'], symbol['y'] + 96), wires, flags)
            if error or negative != ('0',):
                reason = error or 'negative pin is not unambiguously grounded; differential inputs need manual review'
            else:
                labels, error = _labels_at((symbol['x'], symbol['y'] + 16), wires, flags)
                if error or not labels or '0' in labels or any(not re.fullmatch(r'[a-z_][a-z0-9_.$:-]*', label) for label in labels):
                    reason = error or 'no unambiguous labeled input node was found'
                else:
                    candidates.update(f'V({label})' for label in labels)
                    if len(labels) > 1:
                        reason = 'multiple connected labels; choose a reference explicitly'
        if reason:
            ambiguous = True
            notices.append(f'AC excitation source {name} was detected, but {reason}.')
    return ReferenceHints(tuple(sorted(candidates)), tuple(sources), tuple(notices),
                          ambiguous or len(sources) > 1)
