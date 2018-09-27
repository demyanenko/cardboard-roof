import os
from typing import Callable
from enum import Enum
from math import pi, sin, cos, tan, asin, floor, sqrt

import svgwrite

UNIT = svgwrite.cm
UNITS_PER_INCH = 2.54
PT_PER_UNIT = 72 / UNITS_PER_INCH
DOTS_PER_UNIT = 96 / UNITS_PER_INCH


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
        start = (x1 * UNIT, y1 * UNIT)
        end = (x2 * UNIT, y2 * UNIT)
        style = f'stroke:red;stroke-width:{thickness_pt}pt'
        dwg.add(dwg.line(start=start, end=end, style=style))
        return

    # Pattern:
    # o  ----    ----    ----    ----  o
    safe_zone_pt = 3
    dash_length_pt = 7.2
    gap_length_pt = 7.2
    full_line_length_pt = sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2) * PT_PER_UNIT

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

    start = (x_start * UNIT, y_start * UNIT)
    end = (x_end * UNIT, y_end * UNIT)
    style = f'stroke:red;' \
            f'stroke-width:{thickness_pt}pt;' \
            f'stroke-dasharray:{dash_length_pt}pt,{gap_length_pt}pt;' \
            f'stroke-dashoffset:{dash_offset_pt}pt'

    dwg.add(dwg.line(start=start, end=end, style=style))


def lasercutter_line(
        dwg: svgwrite.Drawing,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        line_type: LineType
) -> None:
    return lasercutter_base_line(0.01, dwg, x1, y1, x2, y2, line_type)


def lasercutter_preview_line(
        dwg: svgwrite.Drawing,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        line_type: LineType
) -> None:
    return lasercutter_base_line(2, dwg, x1, y1, x2, y2, line_type)


def miura_ori(
        radius: float,
        beta: float,
        target_width: float,
        target_height: float,
        cell_width: float,
        cell_height: float,
        line_func: Callable[[svgwrite.Drawing, float, float, float, float, LineType], None],
        filename: str
):
    delta = asin(
        (cell_height * sin(beta)) /
        sqrt(radius ** 2 + cell_height ** 2 - 2 * radius * cell_height * cos(beta))
    )
    alpha = beta + delta
    smallest_cell_side = cell_height + cell_width * (tan(beta) - tan(alpha))

    print(f'alpha: {alpha / pi:.2f} pi')
    print(f'delta: {delta / pi:.2f} pi')
    print(f'min cell side: {smallest_cell_side:.2f} units')

    cells_hor = floor(target_width / cell_width)
    cells_vert = floor(target_height / cell_height)
    height_cut = cell_height * tan(alpha)
    width = cells_hor * cell_width
    height = cells_vert * cell_height - height_cut

    assert alpha >= beta
    assert smallest_cell_side >= 0

    if alpha > beta:
        outer_symm_radius = cell_height * sin(alpha) / sin(alpha - beta)
        inner_radius = cell_height * (sin(alpha) / tan(alpha - beta) - cos(alpha))
        outer_radius = sqrt(outer_symm_radius ** 2 + (cell_width * cos(beta)) ** 2)
        thickness = outer_radius - inner_radius

        print(f'Outer radius: {outer_radius:.2f} units')
        print(f'Some radius: {outer_symm_radius:.6f} units')
        print(f'Inner radius: {inner_radius:.2f} units')
        print(f'Thickness: {thickness:.2f} units')
    else:
        print(f'Pattern is straight')

    dwg = svgwrite.Drawing(
        filename=filename,
        size=(width * UNIT, height * UNIT),
        viewBox=f'0 0 {width * DOTS_PER_UNIT} {height * DOTS_PER_UNIT}')

    def clip_x(x):
        return max(0.0, min(x, width))

    def clip_y(y):
        return max(0.0, min(y, height))

    def add_line(start_x, start_y, end_x, end_y, line_type):
        x1 = clip_x(start_x * cell_width)
        y1 = clip_y(start_y * cell_height - height_cut)

        x2 = clip_x(end_x * cell_width)
        y2 = clip_y(end_y * cell_height - height_cut)
        line_func(dwg, x1, y1, x2, y2, line_type)

    def angle_offset(angle):
        return cell_width / cell_height * tan(angle)

    # Edges
    add_line(0, 0, cells_hor, 0, LineType.EDGE)
    add_line(cells_hor, 0, cells_hor, cells_vert, LineType.EDGE)
    add_line(cells_hor, cells_vert, 0, cells_vert, LineType.EDGE)
    add_line(0, cells_vert, 0, 0, LineType.EDGE)

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


def miura_pack(dir: str, filename: str, config: dict) -> None:
    if not os.path.exists(dir):
        os.makedirs(dir)

    miura_ori(
        **config,
        line_func=simulator_line,
        filename=dir + '/preview_' + filename + '.svg'
    )

    miura_ori(
        **config,
        line_func=lasercutter_preview_line,
        filename=dir + '/laser_preview_' + filename + '.svg'
    )

    miura_ori(
        **config,
        line_func=lasercutter_line,
        filename=dir + '/laser_' + filename + '.svg'
    )


def main():
    full_config = {
        'radius': 50,
        'beta': 3/16 * pi,
        'target_width': 167,
        'target_height': 100,
        'cell_width': 3,
        'cell_height': 3
    }

    scale_config = {
        'radius': 12,
        'beta': 3/16 * pi,
        'target_width': 20,
        'target_height': 20,
    }

    for scale in [1, 2, 3, 5]:
        miura_pack('scale', f'{scale}cm', dict(scale_config, cell_width=scale, cell_height=scale))

    height_config = {
        'radius': 12,
        'beta': 3/16 * pi,
        'target_width': 20,
        'target_height': 20,
        'cell_width': 1.5,
    }

    for i in [0.5, 0.75, 1, 1.5]:
        height = i * 1.5
        miura_pack('height', f'{i}-1', dict(height_config, cell_height=height))

    beta_config = {
        'radius': 6.,
        'target_width': 20,
        'target_height': 20,
        'cell_width': 2,
        'cell_height': 2
    }

    for i in range(2, 5):
        beta = i / 16 * pi
        miura_pack('beta', f'{i}-16_pi', dict(beta_config, beta=beta))


if __name__ == '__main__':
    main()
