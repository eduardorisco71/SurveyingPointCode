# -*- coding: utf-8 -*-
#
# Prototype App, converter to dxf
#
# Required PLY (Python Lex-Yacc).
# Required ezdxf.
#
# J. Eduardo Risco 21-03-2019
#

import ezdxf
import ply.lex as lex
import ply.yacc as yacc

from app.geometric_tools import (create_circles, create_curves, create_layers,
                                 create_lines, create_points,
                                 create_rectangles, create_squares,
                                 insert_symbols)
from app.upload_optional_files import (get_config_user, get_symbols,
                                       get_symbols_file_dxf)

topo_layers = set()
error_upload = []
circles = []
squares = []
rectangles = []
lines = []
curves = []
points = []


# Lexer part

tokens = (
    "ID",
    "INT",
    "FLOAT",
    "COMA",
    "COD_GEOM",
    "COD_ELEM_SING",
)

reserved = {
    'I': "COD_GEOM",
    'IC': "COD_GEOM",
    'C': "COD_GEOM",
    'TC': "COD_ELEM_SING",
    'TR': "COD_ELEM_SING",
    'TX': "COD_ELEM_SING",
}


def t_ID(t):
    r'[a-zA-Z]+'
    t.type = reserved.get(t.value, 'ID')
    return t


def t_FLOAT(t):
    r'-?([0-9]*\.[0-9]+)'
    t.value = float(t.value)
    return t


def t_INT(t):
    r'-?[0-9]+'
    t.value = int(t.value)
    return t


t_COMA = r','

t_ignore = r' '


def t_newline(t):
    r'\n+'
    t.lexer.lineno += t.value.count("\n")


def t_error(t):
    raise SyntaxError("syntax error on line %d near '%s'" %
                      (t.lineno, t.value))


lexer_topographycal = lex.lex()

# Parser part


def p_linea(p):
    ''' linea : INT COMA coordenadas COMA codigo '''
    p[0] = (p[1], p[3]) + p[5]


def p_coordenadas(p):
    ''' coordenadas : FLOAT COMA FLOAT COMA FLOAT '''
    p[0] = p[1], p[3], p[5]


def p_codigo(p):
    ''' codigo : codigo_capa codigo_geometrico
                   | codigo_elemento_singular codigo_valor_texto
                   | codigo_capa codigo_no_accesible
                   | codigo_elemento_singular
                   | codigo_capa '''

    if len(p) == 3:
        p[0] = p[1], p[2]
    else:
        p[0] = (p[1],)


def p_codigo_capa(p):
    ''' codigo_capa : ID '''
    p[0] = p[1]


def p_codigo_geometrico(p):
    ''' codigo_geometrico : COD_GEOM '''
    p[0] = p[1]


def p_codigo_elemento_singular(p):
    ''' codigo_elemento_singular :  COD_ELEM_SING '''
    p[0] = p[1]


def p_codigo_valor_texto(p):
    ''' codigo_valor_texto : FLOAT ID
                           | INT ID
                           | FLOAT
                           | INT
                           | ID '''

    if len(p) == 3:
        p[0] = p[1], p[2]
    else:
        p[0] = p[1]


def p_codigo_no_accesible(p):
    ''' codigo_no_accesible : FLOAT
                            | INT
                            | codigo_no_accesible FLOAT
                            | codigo_no_accesible INT  '''

    if len(p) == 3:

        if isinstance(p[1], tuple):
            p[0] = p[1] + (p[2],)
        else:
            p[0] = p[1], p[2]
    else:
        p[0] = p[1]


def p_error(p):
    if p:
        return p.value


def upload_txt(input_file):
    '''
    This function reads a file with topographic survey data,
    translating the points codes in several geometric elements.
    '''

    try:

        global error_upload
        global lines
        global curves
        global topo_layers
        global points
        global circles
        global squares
        global rectangles

        parser = yacc.yacc()
        topo_layers = set()
        dict_layers = {}
        lines = []
        curves = []
        points = []
        line = []
        curve = []
        error_upload = []
        circles = []
        squares = []
        rectangles = []
        layer_code = ""

        f = open(input_file)
        line = f.readline()
        n_line = 0

        while line != "":
            n_line += 1
            # Using the parser
            punto = parser.parse(line, lexer=lexer_topographycal)
            # Detection of incorrect input file
            if not punto:
                # Capturing Errors
                error_upload.append([n_line, line])
            else:
                # Getting the layer code
                if len(punto) == 4 and (punto[2] == "TR" or punto[2] == "TC"):
                    layer_code = punto[3]
                elif punto[2] == "TX":
                    layer_code = punto[3][1]
                else:
                    layer_code = punto[2]
                # Verification that the layers do not exist in the dictionary
                # if they do not exist they are created
                # and the first point is added to that layer
                if layer_code not in topo_layers:
                    dict_layers[layer_code] = [punto]
                    topo_layers.add(layer_code)
                else:
                    # Add points having the same code to their
                    # corresponding element in the dictionary
                    if layer_code in dict_layers:
                        lista = dict_layers.get(layer_code)
                        lista.append(punto)
                        dict_layers[layer_code] = lista
            line = f.readline()
        f.close()

        if error_upload:
            return get_errors_upload()
        else:
           # Decoding of lines, curves and other elements
            for ptos in dict_layers:
                line_started = False
                curve_started = False
                for pto in dict_layers.get(ptos):
                    points.append(pto)
                    if pto[2] not in ('TC', 'TR', 'TX'):
                        if len(pto) > 3 and not isinstance(
                                pto[3], (tuple, int, float)):
                            if pto[3] == 'I':
                                if line_started:
                                    # If another 'I' is found, the line closes
                                    # and another line begins.
                                    lines.append(line)
                                    line = []
                                    line.append(pto)
                                    line_started = True
                                # If there is no line in that layer,
                                # the first line will be created.
                                else:
                                    line = []
                                    line.append(pto)
                                    line_started = True
                            elif pto[3] == 'IC':
                                if curve_started:
                                    # If another 'IC' is found, the curve closes
                                    # and another curve begins.
                                    curves.append(curve)
                                    curve = []
                                    curve.append(pto)
                                    curve_started = True
                                # If there is no curve in that layer,
                                # the first curve will be created.
                                else:
                                    curve = []
                                    curve.append(pto)
                                    curve_started = True
                            # Add points to the curve
                            elif pto[3] == 'C' and curve_started:
                                curve.append(pto)
                        elif len(pto) == 4 and line_started:
                            line.append(pto)
                        # Add points to the line
                        elif line_started:
                            line.append(pto)
                    # Save existing circles
                    elif pto[2] == 'TX':
                        circles.append(pto)
                    # Save existing squares
                    elif pto[2] == 'TC':
                        squares.append(pto)
                    # Save existing rectangles
                    elif pto[2] == 'TR':
                        rectangles.append(pto)

                # If there are no more elements in the layer,
                # lines and curves are closed.
                if line:
                    lines.append(line)
                    line = []
                if curve:
                    curves.append(curve)
                    curve = []
    except (IOError, NameError) as e:
        print(e)
        # completar con return error


# Possible CAD versions to generate a dxf
cad_versions = {
    'DXF 2018': 'AC1032',
    'DXF 2013': 'AC1027',
    'DXF 2010': 'AC1024',
    'DXF 2007': 'AC1021',
    'DXF 2004': 'AC1018',
    'DXF 2000': 'AC1015',
    'DXF R14': 'AC1014',
    'DXF R13': 'AC1012',
    'DXF R12': 'AC1009'}


def configuration_table():
    '''
    This function fills the configuration table of codes, layers, colors 
    and symbols. It connects, if they exist, the files loaded by the user,
    creating an automatic configuration.
    Return a list
    '''

    table_config = []
    for layer_topog in get_layers():
        line = dict()
        line['code'] = layer_topog
        if get_config_user():
            for conf in get_config_user():
                if conf[0] == layer_topog:
                    line['layer'] = conf[1]
                    line['color'] = conf[2]
                    if get_symbols() and len(conf) > 3:
                        line['symbol'] = conf[3]
                    else:
                        line['symbol'] = ''
        else:
            line['layer'] = ''
            line['color'] = (0, 0, 0)
            line['symbol'] = ''

        table_config.append(line)
    print(table_config)    
    return table_config


def config_to_dxf(conf_user_web):
    '''
    This function returns the final configuration generated by the user 
    to create the dxf file.
    '''
    final_config = []

    for d in conf_user_web:
        l_conf = []
        for e in d.values():
            if e == 'No symbol found':
                e = ''
            elif e.find('rgb') == 0:
                e = (e[4:-1])
                t = []
                for i in e.split(','):
                    t.append(int(i))
                e = tuple(t)
            l_conf.append(e)
        final_config.append(l_conf)
    return final_config


def genera_dxf(download_folder, dxf_filename, form_web,
               version=cad_versions['DXF 2004']):
    '''
    This function generates a dxf file.
    '''

    if not get_errors_upload() and not get_errors_square() and (
            not get_errors_rectangle()):

        file_user = config_to_dxf(form_web)
        dwg = ezdxf.new(version)

        # Create the model space.
        msp = dwg.modelspace()

        if get_symbols():
            source_drawing = ezdxf.readfile(get_symbols_file_dxf())
            importer = ezdxf.Importer(source_drawing, dwg)
            importer.import_blocks()
            # Adding symbols to model.
            insert_symbols(msp, get_points(), file_user)

        # Creating required layers.
        create_layers(dwg, file_user)
        # Adding points to model.
        create_points(dwg, msp, get_points())
        # Adding circles to model.
        if get_circles():
            create_circles(msp, get_circles(), file_user)
        # Adding lines to model.
        if get_lines():
            create_lines(msp, get_lines(), file_user)
        # Adding curves to model.
        if get_curves():
            create_curves(msp, get_curves(), file_user)
        # Adding squares to model.
        if get_squares():
            create_squares(msp, get_squares(), file_user)
        # Adding rectangles to model.
        if get_rectangles():
            create_rectangles(msp, get_rectangles(), file_user)

        dwg.saveas(download_folder+'/'+dxf_filename)


def get_errors_upload():
    '''
    This function returns the errors of the input file
    '''

    if error_upload:
        return error_upload
    return False


def get_errors_square():
    '''
    This function returns error, if the number of elements
    defined to form squares, is not correct.
    '''

    if len(squares) % 2 != 0:
        return True
    return False


def get_errors_rectangle():
    '''
    This function returns error, if the number of elements
    defined to form rectangles, is not correct.
    '''

    if len(rectangles) % 3 != 0:
        return True
    return False


def get_layers():
    '''
    This function returns a list with topographic codes.
    '''

    if topo_layers:
        return topo_layers
    return False


def get_points():
    '''
    This function returns a points list .
    '''
    if get_errors_upload():
        return False
    else:
        return points


def get_circles():
    '''
    This function returns a circles list .
    '''
    if get_errors_upload():
        return False
    else:
        return circles


def get_curves():
    '''
    This function returns a splines list .
    '''
    if get_errors_upload():
        return False
    else:
        return curves


def get_lines():
    '''
    This function returns a lines list .
    '''
    if get_errors_upload():
        return False
    else:
        return lines


def get_squares():
    '''
    This function returns a squares list .
    '''
    if get_errors_upload() or get_errors_square():
        return False
    else:
        return squares


def get_rectangles():
    '''
    This function returns a rectangles list .
    '''
    if get_errors_upload() or get_errors_rectangle():
        return False
    else:
        return rectangles
