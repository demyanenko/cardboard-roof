from typing import Callable
from enum import Enum
from math import pi, sin, cos, tan, floor, sqrt

import svgwrite

UNIT = svgwrite.inch
PT_PER_UNIT = 72
DOTS_PER_UNIT = 96


class LineType(Enum):
    VALLEY = 1
    MOUNTAIN = 2
    EDGE = 3


def simulator_line(
        dwg: svgwrite.Drawing,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        line_type: LineType
) -> None:
    if line_type == LineType.VALLEY:
        color = 'blue'
    elif line_type == LineType.MOUNTAIN:
        color = 'red'
    else:
        color = 'black'

    start = (x1 * UNIT, y1 * UNIT)
    end = (x2 * UNIT, y2 * UNIT)
    style = f'stroke:{color};stroke-width:3pt'

    dwg.add(dwg.line(start=start, end=end, style=style))


def lasercutter_base_line(
        thickness_pt: float,
        dwg: svgwrite.Drawing,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        line_type: LineType
) -> None:
    def weighted_average(a, b, t):
        return a * t + b * (1 - t)

    if line_type == LineType.EDGE:
        return

    # Pattern:
    # o  ----    ----    ----    ----  o
    safe_zone_pt = 3
    dash_length_pt = 7.2
    gap_length_pt = 7.2
    full_line_length_pt = sqrt((x2 - x1)**2 + (y2 - y1)**2) * PT_PER_UNIT

    line_length_pt = full_line_length_pt - 2 * safe_zone_pt
    if line_length_pt <= 0:
        return

    t_start = safe_zone_pt / full_line_length_pt
    t_end = 1 - t_start
    x_start = weighted_average(x1, x2, t_start)
    y_start = weighted_average(y1, y2, t_start)
    x_end = weighted_average(x1, x2, t_end)
    y_end = weighted_average(y1, y2, t_end)

    dash_count = 1
    while dash_count * dash_length_pt + (dash_count - 1) * gap_length_pt <= line_length_pt:
        dash_count += 1

    dash_offset_pt = (dash_count * dash_length_pt + (dash_count - 1) * gap_length_pt - line_length_pt) / 2

    # dash_offset = dash_length_pt - ((line_length_pt - dash_length_pt) % (dash_length_pt + gap_length_pt)) / 2

    start = (x_start * UNIT, y_start * UNIT)
    end = (x_end * UNIT, y_end * UNIT)
    style = f'stroke:red;' \
            f'stroke-width:{thickness_pt}pt;' \
            f'stroke-dasharray:{dash_length_pt}pt,{gap_length_pt}pt;' \
            f'stroke-dashoffset:{dash_offset_pt}pt'

    dwg.add(dwg.line(start=start, end=end, style=style))


def lasercutter_line(*args) -> None:
    return lasercutter_base_line(0.01, *args)


def lasercutter_preview_line(*args) -> None:
    return lasercutter_base_line(2, *args)


def miura_ori(line_func: Callable[[svgwrite.Drawing, float, float, float, float, LineType], None]):
    # Geometry
    alpha = 1/4 * pi
    beta = 3/16 * pi
    target_width = 8
    target_height = 10
    cell_height = 1
    cell_width = 1

    cells_hor = floor(target_width / cell_width)
    cells_vert = floor(target_height / cell_height)
    height_cut = cell_height * tan(alpha)
    width = cells_hor * cell_width
    height = cells_vert * cell_height - height_cut

    assert(alpha > beta)
    assert(cell_height + cell_width * (tan(beta) - tan(alpha)) >= 0)

    outer_symm_radius = cell_height * sin(alpha) / sin(alpha - beta)
    inner_radius = cell_height * (sin(alpha) / tan(alpha - beta) - cos(alpha))
    outer_radius = sqrt(outer_symm_radius ** 2 + (cell_width * cos(beta)) ** 2)
    thickness = outer_radius - inner_radius

    print(f'Outer radius: {outer_radius:.2f} in')
    print(f'Inner radius: {inner_radius:.2f} in')
    print(f'Thickness: {thickness:.2f} in')

    dwg = svgwrite.Drawing(
        'test.svg',
        size=(width * UNIT, height * UNIT),
        viewBox=f'0 0 {width * PT_PER_UNIT} {height * PT_PER_UNIT}')

    def clip_x(x):
        return max(0, min(x, width))

    def clip_y(y):
        return max(0, min(y, height))

    def add_line(start_x, start_y, end_x, end_y, line_type):
        x1 = clip_x(start_x * cell_width)
        y1 = clip_y(start_y * cell_height - height_cut)

        x2 = clip_x(end_x * cell_width)
        y2 = clip_y(end_y * cell_height - height_cut)
        line_func(dwg, x1, y1, x2, y2, line_type)

    def angle_offset(angle):
        return cell_width * tan(angle)

    # Edges
    add_line(0, 0, cells_hor, 0, LineType.EDGE)
    add_line(cells_hor, 0, cells_hor, cells_vert, LineType.EDGE)
    add_line(cells_hor, cells_vert, 0, cells_vert, LineType.EDGE)
    add_line(0, cells_hor, 0, 0, LineType.EDGE)

    # grid
    for i in range(cells_hor):
        for j in range(cells_vert):
            offset_left = i % 2
            offset_right = 1 - i % 2
            offset_top = angle_offset([beta, alpha][j % 2])
            offset_bottom = angle_offset([alpha, beta][j % 2])

            x11 = x21 = i
            x12 = x22 = i + 1
            y11 = j + offset_left * offset_top if j > 0 else 0
            y12 = j + offset_right * offset_top if j > 0 else 0
            y21 = j + 1 + offset_left * offset_bottom
            y22 = j + 1 + offset_right * offset_bottom

            if i != cells_hor - 1:
                line_type = [LineType.VALLEY, LineType.MOUNTAIN][(i + j) % 2]
                add_line(x12, y12, x22, y22, line_type)
            if j != cells_vert - 1:
                line_type = [LineType.MOUNTAIN, LineType.VALLEY][j % 2]
                add_line(x21, y21, x22, y22, line_type)

    dwg.save(pretty=True)


def main():
    miura_ori(simulator_line)
    # miura_ori(lasercutter_preview_line)
    # miura_ori(lasercutter_line)


if __name__ == '__main__':
    main()
