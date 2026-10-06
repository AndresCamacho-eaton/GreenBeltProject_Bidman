"""
    Dibujo ASCII de bienvenida (el corredor con una terminal por cabeza del icono de la app).

    ART es el dibujo; COLORS tiene el mismo tamaño y dice el color de cada carácter:
        w = blanco (cuerpo, pantalla)    d = gris (brazo y pierna de atrás)
        g = verde (>_< y líneas de velocidad)    o = naranja (zapatos)
        espacio = color normal de la terminal
"""

ART = r"""
                  .--------------.
          o      / o o o          \
        o       |  .------------.  |
                |  |    >_<     |  |
   ====  ===    |  '------------'  |
                 \______  _______/
     ========          //
                  ____//___
   =====         /    //   \    /
                /    //     \__/
                    //\\
                   //  \\______
        [___]_____//          \\
                               \\
                             [____]
"""

COLORS = r"""
                  wwwwwwwwwwwwwwww
          w      wwwwwwwwwwwwwwwwwww
        w       wwwwwwwwwwwwwwwwwwww
                wwww    ggg     wwww
   gggg  ggg    wwwwwwwwwwwwwwwwwwww
                 wwwwwwwwwwwwwwwwwww
     gggggggg          ww
                  ddddwwwwww
   ggggg         d    ww   w    w
                d    ww     wwww
                    wwww
                   ww  wwwwwwww
        oooooddddddd          ww
                               ww
                             oooooo
"""
