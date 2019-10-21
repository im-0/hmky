#!/usr/bin/env python3

import copy
import importlib
import itertools
import random
import sys


_MAX_BOARD_SIZE = 8


def _print_help():
    print('\n'.join(' ' * 4 + l for l in (
        '?',
        'h',
        '    Print this help message.',
        '',
        'x',
        '    Exit.',
        '',
        'n <W> <H>',
        '    Create board with specified <W>idth and <H>eight.',
        '    <W>idth and <H>eight must be >= 1 and <= %u' % (_MAX_BOARD_SIZE, ),
        '    All cells are set to "1" (enabled) by default.',
        '',
        'c',
        '    Clear board: set all cells to "0" (disabled).',
        '',
        'p',
        '    Print current board.',
        '',
        'pb',
        '    Print current board in binary form.',
        '',
        'r <N>',
        '    Apply <N>umber of random changes to board.',
        '    <N>umber must be >= 1 and <= (Width * Height).',
        '',
        'rr',
        '    Apply random number of random changes to board.',
        '',
        's <ROW1> <ROW2> ... <ROWn>',
        '    Set board state from bit strings.',
        '    Argument format is the same as the output format of command "pb".',
        '',
        'e <XY>',
        '    Set cell with coordinates <X>:<Y> to "1" (enable).',
        '    <X> is specified as letter and must be >= 1 and <= Width.',
        '    <Y> is specified as number and must be >= 1 and <= Height.',
        '',
        'd <XY>',
        '    Set cell with coordinates <X>:<Y> to "0" (disable).',
        '    <X> is specified as letter and must be >= 1 and <= Width.',
        '    <Y> is specified as number and must be >= 1 and <= Height.',
        '',
        'f <XY>',
        '    Flip cells around coordinates <X>:<Y>.',
        '',
        'a',
        '    Automatically solve puzzle and show the solution.',
    )))


def _print_basic_help():
    print('# type "?" or "h" for help')


def _match_cmd(cmd, pattern, argv_out=None):
    cmd_0, cmd = cmd[0], cmd[1:]
    pattern_0, pattern = pattern[0], pattern[1:]

    if cmd_0 != pattern_0:
        return False

    if len(cmd) != len(pattern):
        print('[Error] Invalid number of arguments for command "',
              cmd_0, '": ', len(cmd), ' != ', len(pattern),
              sep='')
        return False

    for cmd_n, pattern_n in zip(cmd, pattern):
        try:
            argv_n = pattern_n(cmd_n)
        except ValueError:
            if hasattr(pattern_n, 'type_name'):
                type_name = pattern_n.type_name()
            else:
                type_name = pattern_n.__name__
            print('[Error] Argument %r is not of type' % (cmd_n, ),
                  type_name)
            return False

        if argv_out is not None:
            argv_out.append(argv_n)

    return True


class _Board(object):
    def _bit_pos(self, x, y):
        return (self._width - x - 1) + (self._height - y - 1) * self._width

    def _bit(self, x, y):
        return 0b1 << self._bit_pos(x, y)

    def _init_patterns(self):
        self._patterns = {}
        self._patterns_bits = {}
        for y in range(self._height):
            for x in range(self._width):
                pat_n = self._bit_pos(x, y)

                pat = self._bit(x, y)
                self._patterns_bits[pat_n] = {pat_n}
                if x:
                    pat |= self._bit(x - 1, y)
                    self._patterns_bits[pat_n].add(self._bit_pos(x - 1, y))
                if x < self._width - 1:
                    pat |= self._bit(x + 1, y)
                    self._patterns_bits[pat_n].add(self._bit_pos(x + 1, y))
                if y:
                    pat |= self._bit(x, y - 1)
                    self._patterns_bits[pat_n].add(self._bit_pos(x, y - 1))
                if y < self._height - 1:
                    pat |= self._bit(x, y + 1)
                    self._patterns_bits[pat_n].add(self._bit_pos(x, y + 1))

                self._patterns[pat_n] = pat

    def __init__(self, width, height):
        self._width = width
        self._height = height

        self._bits = sum(
            self._bit(x, y)
            for y in range(self._height)
            for x in range(self._width))

        self._init_patterns()

    @property
    def n_bits(self):
        return self._width * self._height

    @property
    def width(self):
        return self._width

    @property
    def height(self):
        return self._height

    def __repr__(self):
        str_bits = '{:b}'.format(self._bits).zfill(self.n_bits)
        split_str_bits = []
        for row in range(self._height):
            split_str_bits.append(
                str_bits[row * self._width:(row + 1) * self._width])
        return ' '.join(split_str_bits)

    def is_solved(self):
        return all((self._bits >> n) & 0b1 for n in range(self.n_bits))

    def __str__(self):
        if self.is_solved():
            h_char = '+'
            v_char = '!'
        else:
            h_char = '-'
            v_char = '|'

        h_line = '  ' + h_char * (4 + 3 * (self._width - 1))

        h_coords = '  '
        for x in range(self._width):
            h_coords += ' ' + chr(ord('a') + x) + ' '

        str_board = h_coords + '\n'

        for y in range(self._height):
            str_board += h_line + '\n%u ' % (y + 1, ) + v_char

            for x in range(self._width):
                if self._bits & self._bit(x, y):
                    str_board += '\u2592\u2592'
                else:
                    str_board += '  '
                str_board += v_char

            str_board += '\n'

        str_board += h_line

        return str_board

    def apply_n_rand(self, n_changes):
        for pat in random.sample(list(self._patterns.values()), n_changes):
            self._bits ^= pat

    def apply_pattern(self, x, y):
        self._bits ^= self._patterns[self._bit_pos(x, y)]

    def set_bits(self, bits):
        self._bits = bits

    def set_cell(self, x, y, v):
        if v:
            self._bits |= self._bit(x, y)
        else:
            self._bits &= ~self._bit(x, y)

    def _combine_constraint_sets(self, constraint_sets, bit_n=0,
                                 prev_covered=0b0, prev_constraint=0b0):
        if not constraint_sets:
            yield prev_constraint
            return

        for constraint in constraint_sets[0]:
            covered = self._patterns[bit_n]

            if constraint & prev_covered == prev_constraint & covered:
                for combined in self._combine_constraint_sets(
                        constraint_sets[1:], bit_n + 1, prev_covered | covered,
                        prev_constraint | constraint):
                    yield combined

    def _pattern_bits_to_coords(self, pattern_bits):
        steps = []
        for y in range(self._height - 1, -1, -1):
            for x in range(self._width - 1, -1, -1):
                bit_v = pattern_bits & 0b1
                pattern_bits >>= 1

                if bit_v:
                    steps.append((x, y))

        # Start walking from the top left corner.
        steps.reverse()
        return steps

    def solve(self):
        bits = self._bits

        constraint_sets = []
        for bit_n in range(self.n_bits):
            bit_v = bits & 0b1
            bits >>= 1

            if bit_v:
                # Bit was XORed even number of times.
                lengths = range(0, len(self._patterns_bits[bit_n]) + 1, 2)
            else:
                # Bit was XORed odd number of times.
                lengths = range(1, len(self._patterns_bits[bit_n]) + 1, 2)

            constraint_set = set()
            for l in lengths:
                constraint_set |= set(
                    sum(
                        0b1 << pat_bit_n
                        for pat_bit_n in pat_set)
                    for pat_set in itertools.combinations(
                        self._patterns_bits[bit_n], l))
            constraint_sets.append(constraint_set)

        solutions = list(
            map(self._pattern_bits_to_coords,
                self._combine_constraint_sets(constraint_sets)))
        # TODO: Are there unsolvable puzzle combinations?
        assert len(solutions) > 0, 'Unsolvable puzzle'

        # Shortest solutions first.
        solutions.sort(key=len)
        return solutions


def _check_board(board):
    if board is None:
        print('[Error] No board, please create one')
        return False
    return True


class _Bits(object):
    def __init__(self, width):
        self._width = width

    def type_name(self):
        return 'bits%u' % (self._width, )

    def __call__(self, str_bits):
        if len(str_bits) != self._width:
            raise ValueError()
        return int(str_bits, base=2)


class _Coord(object):
    def __init__(self, board):
        if board is None:
            self._width = None
            self._height = None
        else:
            self._width = board.width
            self._height = board.height

    def type_name(self):
        return 'coord%u_%u' % (self._width, self._height)

    def __call__(self, str_coord):
        if self._width is None:
            raise ValueError()

        if len(str_coord) != 2:
            raise ValueError()
        x, y = str_coord
        x = ord(x) - ord('a')
        y = int(y) - 1

        if x < 0 or x >= self._width:
            raise ValueError()
        if y < 0 or y >= self._height:
            raise ValueError()

        return x, y


def _match_board_set_cmd(cmd, board, argv_out):
    if board is None:
        return _match_cmd(cmd, ('s', ), argv_out)
    else:
        bits_conv = _Bits(board.width)
        return _match_cmd(cmd, ['s'] + [bits_conv] * board.height, argv_out)


def _shell(isatty):
    _print_basic_help()

    board = None

    prev_cmd_had_output = True
    while True:
        if prev_cmd_had_output:
            print()
        prev_cmd_had_output = True

        try:
            cmd = input('> ').lower().split()
            if not isatty:
                print()
        except (EOFError, SystemError, KeyboardInterrupt):
            print()
            break

        if not cmd:
            prev_cmd_had_output = False
            continue

        cmd_argv = []
        if ('?' in cmd) or ('h' in cmd):
            _print_help()
        elif _match_cmd(cmd, ('x', )):
            break
        elif _match_cmd(cmd, ('n', int, int), cmd_argv):
            width, height = cmd_argv
            if (width < 1) or (height < 1):
                print('[Error] Board size must be >= 1')
                continue
            if (width > _MAX_BOARD_SIZE) or (height > _MAX_BOARD_SIZE):
                print('[Error] Board size must be <=', _MAX_BOARD_SIZE)
                continue

            board = _Board(width, height)
            print(board)
        elif _match_cmd(cmd, ('c', )):
            if not _check_board(board):
                continue

            board.set_bits(0)
            print(board)
        elif _match_cmd(cmd, ('p', )):
            if not _check_board(board):
                continue

            print(board)
        elif _match_cmd(cmd, ('pb', )):
            if not _check_board(board):
                continue

            print(repr(board))
        elif _match_cmd(cmd, ('r', int), cmd_argv):
            if not _check_board(board):
                continue

            n_changes, = cmd_argv
            if n_changes < 1:
                print('[Error] Number of random changes must be >= 1')
                continue
            if n_changes > board.n_bits:
                print('[Error] Number of random changes must be <=',
                      board.n_bits)
                continue

            board.apply_n_rand(n_changes)
            print(board)
        elif _match_cmd(cmd, ('rr', )):
            if not _check_board(board):
                continue

            board.apply_n_rand(random.randint(1, board.n_bits))
            print(board)
        elif _match_board_set_cmd(cmd, board, cmd_argv):
            if not _check_board(board):
                continue

            board.set_bits(
                sum(
                    b << n * board.width
                    for b, n in zip(
                        cmd_argv,
                        range(board.height - 1, -1, -1))))
            print(board)
        elif _match_cmd(cmd, ('e', _Coord(board)), cmd_argv):
            if not _check_board(board):
                continue

            (x, y), = cmd_argv
            board.set_cell(x, y, 1)
            print(board)
        elif _match_cmd(cmd, ('d', _Coord(board)), cmd_argv):
            if not _check_board(board):
                continue

            (x, y), = cmd_argv
            board.set_cell(x, y, 0)
            print(board)
        elif _match_cmd(cmd, ('f', _Coord(board)), cmd_argv):
            if not _check_board(board):
                continue

            (x, y), = cmd_argv
            board.apply_pattern(x, y)
            print(board)
        elif _match_cmd(cmd, ('a', )):
            if not _check_board(board):
                continue

            solutions = board.solve()
            if len(solutions) > 1:
                print(
                    'More than one solution found:',
                    ', '.join(str(len(s)) + ' steps' for s in solutions))
                print('Will show one of the shortest.')
                print()
            solution = solutions[0]

            demo = copy.copy(board)
            print('0)')
            print(demo)
            print()

            if not solution:
                print('Already solved!')
                continue

            step_n = 0
            for step_x, step_y in solution:
                step_n += 1
                print(step_n, ') f ',
                      chr(ord('a') + step_x), step_y + 1, sep='')
                demo.apply_pattern(step_x, step_y)
                print(demo)
                print()

            assert demo.is_solved(), 'Solver produced wrong solution'

            print('Steps:')
            step_n = 0
            for step_x, step_y in solution:
                step_n += 1
                print('%2u) f ' % (step_n, ),
                      chr(ord('a') + step_x), step_y + 1, sep='')
        else:
            print('[Error] Unknown command %r' % (' '.join(cmd), ))
            _print_basic_help()


def _main():
    random.seed()

    isatty = sys.stdin.isatty() and sys.stdout.isatty()
    if isatty:
        importlib.import_module('readline')
    _shell(isatty)


_main()
