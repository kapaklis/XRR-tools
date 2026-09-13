"""Launch the magnetization editor with the fitted values below."""
from genx_figure_studio.magnetization import plot_genx_magnetization

# =============================================================
# INPUT FROM GENX
# =============================================================
#
# Replace these numbers with your fitted magn_ang parameters.
#
# Fe1 is assumed to be substrate-adjacent.
#
# =============================================================

angles = [
	14.193413745871922,
	70.55038230148412,
	24.67418873076728,
	83.77518243431047,
	1.022036582922077,
	84.66234771827585,
	-3.080299942816872,
	66.68742986298837,
	-29.29923941182834,
	56.08187253735667
]


# =============================================================
# OPTIONAL MOMENT MAGNITUDES
# =============================================================
#
# In your present GenX model:
#
#   Fe1       -> cp.Fe1_magn
#   Fe2-Fe10  -> cp.Fe_magn
#
# =============================================================

moments = [
    2.0,   # Fe1
    2.0,   # Fe2
    2.0,   # Fe3
    2.0,   # Fe4
    2.0,   # Fe5
    2.0,   # Fe6
    2.0,   # Fe7
    2.0,   # Fe8
    2.0,   # Fe9
    2.0,   # Fe10
]


if __name__ == '__main__':
    import sys
    if '--plot' in sys.argv:
        plot_genx_magnetization(angles, moments, arrow_scale=1.15, save='GenX_magnetization_profile.pdf')
    else:
        from genx_figure_studio.magnetization_app import main
        main(angles, moments)
