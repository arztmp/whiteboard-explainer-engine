"""Original monoline pen glyphs for Latin letters. Distributed under the repository MIT license."""
from math import dist
import re
from .stroke_plan import Stroke, THEME

# Coordinates are centerlines, with a common baseline at y=100 and intentional descenders.
# Each M starts a separate pen stroke. Glyph paths use absolute M/L/Q/C.
GLYPHS = {
    'A': (72, 'M4 100 Q24 50 40 9 Q51 49 67 100 M17 71 Q38 66 58 70'),
    'B': (67, 'M8 100 L10 11 C67 -1 72 49 12 51 C72 40 82 106 8 100'),
    'C': (70, 'M65 24 C52 -1 21 7 12 38 C-2 83 23 111 59 94 L65 88'),
    'D': (73, 'M9 100 L11 11 C87 4 94 110 9 100'),
    'E': (63, 'M59 11 Q35 8 11 13 Q8 58 9 100 Q34 101 58 95 M11 55 Q33 50 52 52'),
    'F': (62, 'M9 101 Q8 56 12 13 Q31 9 59 11 M11 54 Q32 50 50 51'),
    'G': (76, 'M67 26 C48 -7 13 14 9 52 C2 95 31 113 66 94 L68 63 Q53 60 42 63'),
    'H': (72, 'M10 12 Q8 55 8 101 M64 11 Q62 47 63 100 M10 55 Q35 49 62 52'),
    'I': (34, 'M18 11 Q16 50 16 100'),
    'J': (61, 'M52 11 Q52 45 48 80 C41 111 12 106 6 87'),
    'K': (68, 'M11 11 Q7 62 9 100 M61 13 Q41 34 14 54 Q38 74 62 100'),
    'L': (62, 'M11 11 Q7 61 9 96 Q31 103 58 93'),
    'M': (89, 'M7 100 L14 12 Q31 46 43 75 Q58 42 73 11 L81 100'),
    'N': (73, 'M8 100 L13 12 Q38 56 63 98 L65 11'),
    'O': (77, 'M58 15 C27 -9 6 29 7 59 C7 91 21 105 44 101 C78 98 79 38 58 15'),
    'P': (67, 'M10 100 L12 13 C69 4 81 62 12 57'),
    'Q': (77, 'M58 15 C27 -9 6 29 7 59 C7 91 21 105 44 101 C78 98 79 38 58 15 M45 78 Q57 97 71 107'),
    'R': (71, 'M10 101 L12 12 C74 -3 76 62 12 56 M34 56 Q49 75 66 101'),
    'S': (68, 'M63 25 C52 4 18 5 11 30 C4 53 48 55 58 71 C79 102 24 113 8 89'),
    'T': (69, 'M3 16 Q36 7 66 12 M35 13 Q32 59 32 100'),
    'U': (73, 'M11 12 C5 58 3 104 34 101 C66 100 65 50 64 12'),
    'V': (71, 'M6 12 Q22 63 33 100 Q51 58 65 12'),
    'W': (96, 'M5 13 Q12 60 23 99 Q38 61 48 38 Q53 66 67 100 Q84 61 91 10'),
    'X': (69, 'M9 12 Q35 57 65 100 M62 13 Q40 46 6 101'),
    'Y': (68, 'M4 12 Q20 39 34 56 Q50 36 63 11 M34 56 L32 100'),
    'Z': (69, 'M7 16 Q34 10 61 11 Q41 51 9 98 Q35 102 64 96'),
    'a': (54, 'M43 48 C27 34 10 49 7 70 C0 104 30 112 43 87 L48 40 M43 85 Q43 101 51 99'),
    'b': (54, 'M11 9 Q7 60 9 99 C38 111 58 82 46 52 C37 38 20 43 10 65'),
    'c': (49, 'M44 51 C34 34 12 48 8 66 C0 98 25 112 45 92'),
    'd': (56, 'M44 48 C23 33 7 55 7 78 C6 107 33 110 44 88 M49 9 Q42 49 44 89 Q45 100 52 99'),
    'e': (51, 'M9 72 C29 72 50 63 45 50 C36 31 11 46 7 68 C1 99 29 111 47 91'),
    'f': (36, 'M11 102 Q16 60 18 26 C20 9 27 3 35 12 M4 52 Q17 48 34 48'),
    'g': (55, 'M44 48 C28 34 11 47 7 70 C2 100 28 111 43 85 M48 42 Q43 77 43 111 C43 143 20 148 8 128'),
    'h': (55, 'M11 10 Q8 54 7 100 M10 68 C24 32 49 42 47 64 L46 100'),
    'i': (26, 'M11 46 Q7 81 9 96 Q13 101 20 97 M13 22 L13 25'),
    'j': (29, 'M18 44 L14 113 C13 137 1 139 -7 128 M20 22 L20 25'),
    'k': (52, 'M10 9 L7 100 M46 43 Q32 52 12 72 Q28 81 48 100'),
    'l': (27, 'M13 9 Q7 54 8 90 Q9 103 22 98'),
    'm': (82, 'M9 44 L7 100 M9 64 C22 35 42 39 41 64 L40 100 M42 63 C55 36 76 40 74 63 L73 100'),
    'n': (55, 'M10 44 L8 100 M10 65 C26 33 49 39 47 63 L46 100'),
    'o': (54, 'M39 46 C22 33 7 51 6 73 C3 92 14 103 29 101 C49 100 55 62 39 46'),
    'p': (55, 'M10 44 L6 138 M10 65 C29 29 54 42 49 72 C46 97 29 108 8 96'),
    'q': (55, 'M43 48 C26 33 8 48 6 72 C4 100 28 112 42 86 M47 44 L41 137'),
    'r': (43, 'M10 45 L8 99 M11 65 Q22 40 38 45'),
    's': (46, 'M42 51 C31 35 9 40 8 55 C7 69 37 72 38 84 C42 102 18 108 6 92'),
    't': (36, 'M17 22 Q11 58 11 85 Q9 105 30 96 M3 51 Q18 47 33 48'),
    'u': (56, 'M10 44 C4 70 3 102 20 101 Q35 101 46 76 M49 44 Q44 73 46 97'),
    'v': (51, 'M7 45 Q12 77 23 100 Q40 76 47 44'),
    'w': (76, 'M6 44 Q10 74 20 100 Q35 82 39 64 Q42 84 52 100 Q65 77 71 44'),
    'x': (51, 'M8 45 Q23 73 46 100 M46 45 Q31 70 6 101'),
    'y': (53, 'M7 45 Q11 80 26 94 M48 45 Q39 98 14 136'),
    'z': (50, 'M7 49 Q25 43 44 45 Q28 70 6 99 Q26 102 46 95'),
    '.': (22, 'M9 96 L10 99'),
    ',': (22, 'M12 94 Q15 101 6 111'),
    '!': (24, 'M14 13 L10 76 M10 96 L10 99'),
    '?': (56, 'M7 29 C12 5 48 6 49 29 Q52 44 33 56 Q25 63 26 76 M26 96 L26 99'),
}


def handwriting(text, x, baseline, size, *, width=4.5, tracking=6, word_gap=35,
                line_height=1.43, max_width=None, color=THEME["navy"]):
    """Return strokes and objective layout metrics for supported Latin glyphs."""
    unit = size / 100
    width_of = lambda word: sum(GLYPHS[c][0] + tracking for c in word)
    lines = []
    for paragraph in text.split("\n"):
        current = []
        used = 0
        for word in paragraph.split():
            extra = width_of(word) + (word_gap if current else 0)
            if current and max_width and (used + extra) * unit > max_width:
                lines.append(current)
                current = []
                used = 0
                extra = width_of(word)
            current.append(word)
            used += extra
        if current:
            lines.append(current)
    output, measures = [], []
    for row, words in enumerate(lines):
        offset = x
        top = baseline - size + row * size * line_height
        for word in words:
            for char in word:
                advance, drawing = GLYPHS[char]
                for part in drawing.split("M")[1:]:
                    points = [tuple(map(float, xy.split())) for xy in re.findall(r"-?\d+(?:\.\d+)? -?\d+(?:\.\d+)?", part)]
                    world = [(offset + px * unit, top + py * unit) for px, py in points]
                    coords = iter(world)
                    d = "M" + re.sub(r"-?\d+(?:\.\d+)? -?\d+(?:\.\d+)?",
                                     lambda _: "%.3f %.3f" % next(coords), part)
                    length = sum(dist(a, b) for a, b in zip(world, world[1:])) * .78
                    output.append(Stroke(d, world[0], world[-1], length, width, color=color))
                offset += (advance + tracking) * unit
            offset += word_gap * unit
        measures.append({"text": " ".join(words), "baseline": round(top + size, 3),
                         "width": round(offset - x - word_gap * unit, 3)})
    return output, {"lines": measures, "trackingPx": tracking * unit,
                    "wordGapPx": word_gap * unit, "lineHeightPx": line_height * size,
                    "strokeCount": len(output)}

GLYPHS.update({
    "0": (60, "M42 14 C16 1 7 31 7 58 C5 88 16 105 34 101 C57 98 59 29 42 14"),
    "1": (43, "M8 31 L27 13 Q24 56 24 100 M9 101 L37 100"),
    "2": (61, "M8 32 C16 4 55 5 53 32 C51 54 15 72 8 99 Q32 101 55 96"),
    "3": (59, "M9 19 C27 3 55 9 47 34 Q42 52 24 53 C56 51 60 82 44 95 Q26 111 8 93"),
    "4": (61, "M42 12 L7 68 Q31 68 55 65 M44 16 L42 100"),
    "5": (58, "M52 13 L15 13 L11 53 C35 40 54 56 50 80 C47 101 24 108 9 94"),
    "6": (60, "M49 15 C25 6 9 38 8 65 C7 92 18 106 36 100 C57 93 56 62 37 55 Q21 48 9 70"),
    "7": (59, "M7 17 Q30 10 54 13 Q28 58 21 101"),
    "8": (59, "M25 56 C-2 32 16 7 35 13 C58 20 57 42 25 57 C-7 75 8 106 33 101 C60 96 62 75 25 56"),
    "9": (60, "M52 50 C50 13 31 7 17 17 C0 30 6 58 22 65 Q41 70 52 52 C50 81 39 100 20 104"),
    "+": (62, "M7 57 L55 57 M31 33 L31 81"),
    "-": (52, "M9 57 L44 57"),
    "×": (60, "M13 38 L47 77 M46 38 L13 77"),
    "÷": (62, "M7 57 L55 57 M31 36 L31 39 M31 75 L31 78"),
    "=": (62, "M8 47 L54 47 M8 66 L54 66"),
    "≈": (70, "M9 49 C25 31 42 63 61 45 M9 68 C25 50 42 82 61 64"),
})

# Scientific symbols use the same centerline representation as ordinary handwriting.
GLYPHS.update({
    "−": GLYPHS["-"],
    "Δ": (77, "M7 98 L39 12 L71 98 L7 98"),
    "ω": (78, "M18 43 C2 63 4 103 22 101 Q38 98 39 66 C38 92 42 105 57 99 C74 94 76 62 63 44"),
    "π": (72, "M7 50 Q34 42 66 48 M23 49 Q23 76 16 99 M51 48 Q47 70 48 88 Q50 105 64 98"),
    "∑": (83, "M75 10 L9 10 L49 53 L9 99 L75 99"),
    "∫": (52, "M48 9 C34 -5 27 10 25 30 Q22 58 20 84 C19 102 11 112 3 101"),
})
