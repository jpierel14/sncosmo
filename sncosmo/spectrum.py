# Licensed under a 3-clause BSD style license - see LICENSE.rst

import numpy as np
import astropy.units as u
import astropy.constants as const
from scipy.interpolate import splrep, splev

from .bandpasses import get_bandpass
from .utils import integration_grid
from .constants import SPECTRUM_BANDFLUX_SPACING, HC_ERG_AA

__all__ = ['Spectrum']

FLAMBDA_UNIT = u.erg / u.s / u.cm**2 / u.AA


class Spectrum(object):
    """A spectrum, representing wavelength and spectral density values.

    Parameters
    ----------
    wave : list_like
        Wavelength values.
    flux : list_like
        Spectral flux density values.
    wave_unit : `~astropy.units.Unit`
        Unit on wavelength.
    unit : `~astropy.units.BaseUnit`
        For now, only units with flux density in energy (not photon counts).
    """

    def __init__(self, wave, flux, wave_unit=u.AA,
                 unit=(u.erg / u.s / u.cm**2 / u.AA)):
        self.wave = np.asarray(wave, dtype=np.float64)
        self.flux = np.asarray(flux, dtype=np.float64)
        if self.wave.shape != self.flux.shape:
            raise ValueError('shape of wavelength and flux must match')
        if self.wave.ndim != 1:
            raise ValueError('only 1-d arrays supported')

        # internally, wavelength is in Angstroms:
        if wave_unit != u.AA:
            self.wave = wave_unit.to(u.AA, self.wave, u.spectral())
        self._wave_unit = u.AA

        # internally, flux is in F_lambda:
        if unit != FLAMBDA_UNIT:
            self.flux = unit.to(FLAMBDA_UNIT, self.flux,
                                u.spectral_density(u.AA, self.wave))
        self._unit = FLAMBDA_UNIT

        # Set up interpolation.
        # This appears to be the fastest-evaluating interpolant in
        # scipy.interpolate.
        self._tck = splrep(self.wave, self.flux, k=1)

    def bandflux(self, band):
        """Perform synthentic photometry in a given bandpass.

        The bandpass transmission is interpolated onto the wavelength grid
        of the spectrum. The result is a weighted sum of the spectral flux
        density values (weighted by transmission values).

        Parameters
        ----------
        band : Bandpass object or name of registered bandpass.

        Returns
        -------
        bandflux : float
            Total flux in ph/s/cm^2. If part of bandpass falls
            outside the spectrum, `None` is returned instead.
        bandfluxerr : float
            Error on flux. Only returned if the `error` attribute is not
            `None`.
        """

        # TODO: There is some duplication between this method and
        # models._bandflux_single.

        band = get_bandpass(band)

        # Check that bandpass wavelength range is fully contained in spectrum
        # wavelength range.
        if (band.minwave() < self.wave[0] or band.maxwave() > self.wave[-1]):
            raise ValueError('bandpass {0!r:s} [{1:.6g}, .., {2:.6g}] '
                             'outside spectral range [{3:.6g}, .., {4:.6g}]'
                             .format(band.name, band.minwave(), band.maxwave(),
                                     self.wave[0], self.wave[-1]))

        # Set up wavelength grid. Spacing (dwave) evenly divides the bandpass,
        # closest to 5 angstroms without going over.
        wave, dwave = integration_grid(band.minwave(), band.maxwave(),
                                       SPECTRUM_BANDFLUX_SPACING)
        trans = band(wave)
        f = splev(wave, self._tck, ext=1)

        return np.sum(wave * trans * f) * dwave / HC_ERG_AA
