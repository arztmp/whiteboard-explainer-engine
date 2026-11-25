from engine.scientific import _vertical_points, formula_strokes


def test_fraction_leaves_room_for_scripts():
    formula = ("fraction", ("sub", "m", "1"), ("sup", "r", "2"))
    paths = formula_strokes(formula, 0, 0, 100, color="black")
    bar_index = next(i for i, stroke in enumerate(paths)
                     if stroke.start[0] == 0 and stroke.start[1] == stroke.end[1])
    bar_y = paths[bar_index].start[1]
    assert max(_vertical_points(paths[:bar_index])) <= bar_y - 12
    assert min(_vertical_points(paths[bar_index+1:])) >= bar_y + 12
