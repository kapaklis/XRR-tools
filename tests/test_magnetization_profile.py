"""Scientific checks for the depth-aligned magnetization view."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch
import numpy as np
import pytest
from magnetization_profile import plot_genx_magnetization


def test_fitted_values_order_and_zero_moments_are_preserved(tmp_path):
    output = tmp_path / 'moments.pdf'
    fig = plot_genx_magnetization([3, 91, -45], [0, 2, 1], save=output, show=False, view="profile")
    np.testing.assert_allclose(fig.axes[2].collections[0].get_offsets(), [[3, 25], [91, 56], [-45, 87]])
    glyphs = fig.axes[1].child_axes
    assert len(glyphs) == 3
    assert [sum(isinstance(p, FancyArrowPatch) for p in ax.patches) for ax in glyphs] == [1, 2, 2]
    assert all(ax.get_aspect() == 1 for ax in glyphs)
    assert output.read_bytes().startswith(b'%PDF')
    plt.close(fig)
    fig = plot_genx_magnetization([0], [0], show=False, view="profile")
    assert sum(isinstance(p, FancyArrowPatch) for p in fig.axes[1].child_axes[0].patches) == 1
    plt.close(fig)


@pytest.mark.parametrize('angles,moments', [([], None), ([1, 2], [1]), ([np.nan], None), ([0], [-1])])
def test_invalid_profiles_are_rejected(angles, moments):
    with pytest.raises(ValueError):
        plot_genx_magnetization(angles, moments, show=False, view="profile")


def test_stack_has_unobscured_moments_and_keeps_layer_order(tmp_path):
    fig = plot_genx_magnetization([3, 91, -45], [0, 2, 1], show=False,
                                  save=tmp_path / 'stack.svg')
    ax = fig.axes[0]
    arrows = [p for p in ax.patches if isinstance(p, FancyArrowPatch)]
    assert len(arrows) == 3  # Two nonzero moments and the applied field.
    assert all(p.get_zorder() >= 20 for p in arrows)
    labels = {t.get_text(): t.get_position() for t in ax.texts}
    assert labels['Fe1'][1] < labels['Fe2'][1] < labels['Fe3'][1]
    assert all(label in labels for label in ('3°', '91°', '-45°', 'm = 0 (zero)'))
    assert (tmp_path / 'stack.svg').read_text().find('<svg') >= 0
    plt.close(fig)
