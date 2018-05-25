# Copyright (c) 2017-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree. An additional grant
# of patent rights can be found in the PATENTS file in the same directory.

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import itertools

import numpy as np
import pandas as pd

# fb-block 1 start
import os
from unittest import TestCase
from fbprophet import Prophet
from fbprophet import diagnostics

DATA_all = pd.read_csv(
    os.path.join(os.path.dirname(__file__), 'data.csv'), parse_dates=['ds']
)
DATA = DATA_all.head(100)
# fb-block 1 end
# fb-block 2


class TestDiagnostics(TestCase):

    def __init__(self, *args, **kwargs):
        super(TestDiagnostics, self).__init__(*args, **kwargs)
        # Use first 100 record in data.csv
        self.__df = DATA

    def test_simulated_historical_forecasts(self):
        m = Prophet()
        m.fit(self.__df)
        k = 2
        for p in [1, 10]:
            for h in [1, 3]:
                period = '{} days'.format(p)
                horizon = '{} days'.format(h)
                df_shf = diagnostics.simulated_historical_forecasts(
                    m, horizon=horizon, k=k, period=period)
                # All cutoff dates should be less than ds dates
                self.assertTrue((df_shf['cutoff'] < df_shf['ds']).all())
                # The unique size of output cutoff should be equal to 'k'
                self.assertEqual(len(np.unique(df_shf['cutoff'])), k)
                self.assertEqual(
                    max(df_shf['ds'] - df_shf['cutoff']),
                    pd.Timedelta(horizon),
                )
                dc = df_shf['cutoff'].diff()
                dc = dc[dc > pd.Timedelta(0)].min()
                self.assertTrue(dc >= pd.Timedelta(period))
                # Each y in df_shf and self.__df with same ds should be equal
                df_merged = pd.merge(df_shf, self.__df, 'left', on='ds')
                self.assertAlmostEqual(
                    np.sum((df_merged['y_x'] - df_merged['y_y']) ** 2), 0.0)

    def test_simulated_historical_forecasts_logistic(self):
        m = Prophet(growth='logistic')
        df = self.__df.copy()
        df['cap'] = 40
        m.fit(df)
        df_shf = diagnostics.simulated_historical_forecasts(
            m, horizon='3 days', k=2, period='3 days')
        # All cutoff dates should be less than ds dates
        self.assertTrue((df_shf['cutoff'] < df_shf['ds']).all())
        # The unique size of output cutoff should be equal to 'k'
        self.assertEqual(len(np.unique(df_shf['cutoff'])), 2)
        # Each y in df_shf and self.__df with same ds should be equal
        df_merged = pd.merge(df_shf, df, 'left', on='ds')
        self.assertAlmostEqual(
            np.sum((df_merged['y_x'] - df_merged['y_y']) ** 2), 0.0)

    def test_simulated_historical_forecasts_extra_regressors(self):
        m = Prophet()
        m.add_seasonality(name='monthly', period=30.5, fourier_order=5)
        m.add_regressor('extra')
        df = self.__df.copy()
        df['cap'] = 40
        df['extra'] = range(df.shape[0])
        m.fit(df)
        df_shf = diagnostics.simulated_historical_forecasts(
            m, horizon='3 days', k=2, period='3 days')
        # All cutoff dates should be less than ds dates
        self.assertTrue((df_shf['cutoff'] < df_shf['ds']).all())
        # The unique size of output cutoff should be equal to 'k'
        self.assertEqual(len(np.unique(df_shf['cutoff'])), 2)
        # Each y in df_shf and self.__df with same ds should be equal
        df_merged = pd.merge(df_shf, df, 'left', on='ds')
        self.assertAlmostEqual(
            np.sum((df_merged['y_x'] - df_merged['y_y']) ** 2), 0.0)

    def test_simulated_historical_forecasts_default_value_check(self):
        m = Prophet()
        m.fit(self.__df)
        # Default value of period should be equal to 0.5 * horizon
        df_shf1 = diagnostics.simulated_historical_forecasts(
            m, horizon='10 days', k=1)
        df_shf2 = diagnostics.simulated_historical_forecasts(
            m, horizon='10 days', k=1, period='5 days')
        self.assertAlmostEqual(
            ((df_shf1['y'] - df_shf2['y']) ** 2).sum(), 0.0)
        self.assertAlmostEqual(
            ((df_shf1['yhat'] - df_shf2['yhat']) ** 2).sum(), 0.0)

    def test_cross_validation(self):
        m = Prophet()
        m.fit(self.__df)
        # Calculate the number of cutoff points(k)
        horizon = pd.Timedelta('4 days')
        period = pd.Timedelta('10 days')
        k = 5
        df_cv = diagnostics.cross_validation(
            m, horizon='4 days', period='10 days', initial='90 days')
        # The unique size of output cutoff should be equal to 'k'
        self.assertEqual(len(np.unique(df_cv['cutoff'])), k)
        self.assertEqual(max(df_cv['ds'] - df_cv['cutoff']), horizon)
        dc = df_cv['cutoff'].diff()
        dc = dc[dc > pd.Timedelta(0)].min()
        self.assertTrue(dc >= period)

    def test_cross_validation_default_value_check(self):
        m = Prophet()
        m.fit(self.__df)
        # Default value of initial should be equal to 3 * horizon
        df_cv1 = diagnostics.cross_validation(
            m, horizon='32 days', period='10 days')
        df_cv2 = diagnostics.cross_validation(
            m, horizon='32 days', period='10 days', initial='96 days')
        self.assertAlmostEqual(
            ((df_cv1['y'] - df_cv2['y']) ** 2).sum(), 0.0)
        self.assertAlmostEqual(
            ((df_cv1['yhat'] - df_cv2['yhat']) ** 2).sum(), 0.0)

    def test_performance_metrics(self):
        m = Prophet()
        m.fit(self.__df)
        df_cv = diagnostics.cross_validation(
            m, horizon='4 days', period='10 days', initial='90 days')
        # Aggregation level none
        df_none = diagnostics.performance_metrics(df_cv, rolling_window=0)
        self.assertEqual(
            set(df_none.columns),
            {'horizon', 'coverage', 'mae', 'mape', 'mse', 'rmse'},
        )
        self.assertEqual(df_none.shape[0], 14)
        # Aggregation level 0.2
        df_horizon = diagnostics.performance_metrics(df_cv, rolling_window=0.2)
        self.assertEqual(len(df_horizon['horizon'].unique()), 4)
        self.assertEqual(df_horizon.shape[0], 13)
        # Aggregation level all
        df_all = diagnostics.performance_metrics(df_cv, rolling_window=1)
        self.assertEqual(df_all.shape[0], 1)
        for metric in ['mse', 'mape', 'mae', 'coverage']:
            self.assertEqual(df_all[metric].values[0], df_none[metric].mean())
        # Custom list of metrics
        df_horizon = diagnostics.performance_metrics(
            df_cv, metrics=['coverage', 'mse'],
        )
        self.assertEqual(
            set(df_horizon.columns),
            {'coverage', 'mse', 'horizon'},
        )

    def test_copy(self):
        df = DATA_all.copy()
        df['cap'] = 200.
        df['binary_feature'] = [0] * 255 + [1] * 255
        # These values are created except for its default values
        holiday = pd.DataFrame(
            {'ds': pd.to_datetime(['2016-12-25']), 'holiday': ['x']})
        products = itertools.product(
            ['linear', 'logistic'],  # growth
            [None, pd.to_datetime(['2016-12-25'])],  # changepoints
            [3],  # n_changepoints
            [0.9],  # changepoint_range
            [True, False],  # yearly_seasonality
            [True, False],  # weekly_seasonality
            [True, False],  # daily_seasonality
            [None, holiday],  # holidays
            ['additive', 'multiplicative'],  # seasonality_mode
            [1.1],  # seasonality_prior_scale
            [1.1],  # holidays_prior_scale
            [0.1],  # changepoint_prior_scale
            [100],  # mcmc_samples
            [0.9],  # interval_width
            [200]  # uncertainty_samples
        )
        # Values should be copied correctly
        for product in products:
            m1 = Prophet(*product)
            m1.history = m1.setup_dataframe(
                df.copy(), initialize_scales=True)
            m1.set_auto_seasonalities()
            m2 = diagnostics.prophet_copy(m1)
            self.assertEqual(m1.growth, m2.growth)
            self.assertEqual(m1.n_changepoints, m2.n_changepoints)
            self.assertEqual(m1.changepoint_range, m2.changepoint_range)
            self.assertEqual(m1.changepoints, m2.changepoints)
            self.assertEqual(False, m2.yearly_seasonality)
            self.assertEqual(False, m2.weekly_seasonality)
            self.assertEqual(False, m2.daily_seasonality)
            self.assertEqual(
                m1.yearly_seasonality, 'yearly' in m2.seasonalities)
            self.assertEqual(
                m1.weekly_seasonality, 'weekly' in m2.seasonalities)
            self.assertEqual(
                m1.daily_seasonality, 'daily' in m2.seasonalities)
            if m1.holidays is None:
                self.assertEqual(m1.holidays, m2.holidays)
            else:
                self.assertTrue((m1.holidays == m2.holidays).values.all())
            self.assertEqual(m1.seasonality_mode, m2.seasonality_mode)
            self.assertEqual(m1.seasonality_prior_scale, m2.seasonality_prior_scale)
            self.assertEqual(m1.changepoint_prior_scale, m2.changepoint_prior_scale)
            self.assertEqual(m1.holidays_prior_scale, m2.holidays_prior_scale)
            self.assertEqual(m1.mcmc_samples, m2.mcmc_samples)
            self.assertEqual(m1.interval_width, m2.interval_width)
            self.assertEqual(m1.uncertainty_samples, m2.uncertainty_samples)

        # Check for cutoff and custom seasonality and extra regressors
        changepoints = pd.date_range('2012-06-15', '2012-09-15')
        cutoff = pd.Timestamp('2012-07-25')
        m1 = Prophet(changepoints=changepoints)
        m1.add_seasonality('custom', 10, 5)
        m1.add_regressor('binary_feature')
        m1.fit(df)
        m2 = diagnostics.prophet_copy(m1, cutoff=cutoff)
        changepoints = changepoints[changepoints <= cutoff]
        self.assertTrue((changepoints == m2.changepoints).all())
        self.assertTrue('custom' in m2.seasonalities)
        self.assertTrue('binary_feature' in m2.extra_regressors)
