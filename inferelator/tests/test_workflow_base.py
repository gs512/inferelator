"""
Test base workflow stepwise.
"""

import unittest
import os
import tempfile
import shutil
import numpy as np
import pandas as pd
import pandas.testing as pdt

from inferelator import workflow
from inferelator import default
from inferelator.regression.base_regression import RegressionWorkflow
from inferelator.distributed.inferelator_mp import MPControl
from inferelator.preprocessing.metadata_parser import MetadataParserBranching

my_dir = os.path.dirname(__file__)


class TestWorkflowLoadData(unittest.TestCase):

    def setUp(self):
        self.workflow = workflow.WorkflowBase()
        self.workflow.input_dir = os.path.join(my_dir, "../../data/dream4")
        self.workflow.expression_matrix_file = default.DEFAULT_EXPRESSION_FILE
        self.workflow.tf_names_file = default.DEFAULT_TFNAMES_FILE
        self.workflow.meta_data_file = default.DEFAULT_METADATA_FILE
        self.workflow.priors_file = default.DEFAULT_PRIORS_FILE
        self.workflow.gold_standard_file = default.DEFAULT_GOLDSTANDARD_FILE

    def tearDown(self):
        del self.workflow

    def test_load_expression(self):
        self.workflow.read_expression()
        self.assertEqual(self.workflow.expression_matrix.shape, (100, 421))
        np.testing.assert_allclose(self.workflow.expression_matrix.sum().sum(), 13507.22145160)

    def test_load_tf_names(self):
        self.workflow.read_tfs()
        print(self.workflow.tf_names)
        self.assertEqual(len(self.workflow.tf_names), 100)
        tf_names = list(map(lambda x: "G" + str(x), list(range(1, 101))))
        self.assertListEqual(self.workflow.tf_names, tf_names)

    def test_load_priors_gs(self):
        self.workflow.read_priors()
        self.assertEqual(self.workflow.priors_data.shape, (100, 100))
        self.assertEqual(self.workflow.gold_standard.shape, (100, 100))
        self.assertTrue(all(self.workflow.priors_data.index == self.workflow.priors_data.columns))
        self.assertTrue(all(self.workflow.gold_standard.index == self.workflow.gold_standard.columns))

        self.workflow.priors_file = None
        self.workflow.priors_data = None
        self.workflow.gold_standard_file = None
        self.workflow.gold_standard = None

        with self.assertRaises(ValueError):
            self.workflow.validate_data()

    def test_load_metadata(self):
        self.workflow.read_metadata()
        self.assertEqual(self.workflow.meta_data.shape, (421, 5))

    def test_make_metadata(self):
        self.workflow.read_expression()
        self.workflow.meta_data_file = None
        self.workflow.read_metadata()
        self.assertEqual(self.workflow.meta_data.shape, (421, 4))

    def test_extract_metadata(self):
        self.workflow.read_expression()
        meta_data = MetadataParserBranching.create_default_meta_data(self.workflow.expression_matrix)
        gene_list = self.workflow.expression_matrix.index.tolist()

        self.workflow.expression_matrix = self.workflow.expression_matrix.transpose()
        self.workflow.expression_matrix_columns_are_genes = True
        self.workflow.extract_metadata_from_expression_matrix = True
        self.workflow.expression_matrix = pd.concat([self.workflow.expression_matrix, meta_data], axis=1)
        self.workflow.expression_matrix_metadata = meta_data.columns.tolist()

        self.workflow.read_metadata()

        pdt.assert_frame_equal(self.workflow.meta_data, meta_data)
        self.assertListEqual(self.workflow.expression_matrix.columns.tolist(), gene_list)

    def test_load_gene_metadata(self):
        self.workflow.input_dir = tempfile.mkdtemp()
        self.workflow.gene_metadata_file = "genes.tsv"
        self.workflow.gene_list_index = "SystematicName"
        genes = pd.DataFrame({"SystematicName": ["gene1", "gene2", "gene3", "gene4", "gene7", "gene6"]})
        genes.to_csv(os.path.join(self.workflow.input_dir, "genes.tsv"), sep="\t", index=False)

        self.workflow.read_genes()
        pdt.assert_frame_equal(self.workflow.gene_metadata, genes)

        self.workflow.gene_list_index = None
        with self.assertRaises(ValueError):
            self.workflow.validate_data()

        self.workflow.gene_list_index = "SillyName"
        with self.assertRaises(ValueError):
            self.workflow.validate_data()

        shutil.rmtree(self.workflow.input_dir)

    def test_get_data(self):
        self.workflow.get_data()
        self.assertTrue(self.workflow.expression_matrix is not None)
        self.assertTrue(self.workflow.priors_data is not None)
        self.assertTrue(self.workflow.gold_standard is not None)
        self.assertTrue(self.workflow.tf_names is not None)
        self.assertTrue(self.workflow.meta_data is not None)


class TestWorkflowFunctions(unittest.TestCase):
    data = None

    @classmethod
    def setUpClass(cls):
        cls.data = workflow.WorkflowBase()
        cls.data.input_dir = os.path.join(my_dir, "../../data/dream4")
        cls.data.expression_matrix_file = "expression.tsv"
        cls.data.meta_data_file = "meta_data.tsv"
        cls.data.tf_names_file = "tf_names.tsv"
        cls.data.priors_file = "gold_standard.tsv"
        cls.data.gold_standard_file = "gold_standard.tsv"
        cls.data.get_data()

    def setUp(self):
        self.workflow = workflow.WorkflowBase()
        self.workflow.priors_data = self.data.priors_data.copy()
        self.workflow.gold_standard = self.data.gold_standard.copy()
        self.workflow.expression_matrix = self.data.expression_matrix.copy()
        self.workflow.tf_names = self.data.tf_names
        self.workflow.input_dir = os.path.join(my_dir, "../../data/dream4")

    def test_multiprocessing_init(self):
        MPControl.shutdown()
        self.workflow.multiprocessing_controller = "local"
        self.workflow.initialize_multiprocessing()
        self.assertTrue(MPControl.is_initialized)

    def test_abstractness(self):
        with self.assertRaises(NotImplementedError):
            self.workflow.startup()
        with self.assertRaises(NotImplementedError):
            self.workflow.startup_run()
        with self.assertRaises(NotImplementedError):
            self.workflow.startup_finish()
        with self.assertRaises(NotImplementedError):
            self.workflow.run()
        with self.assertRaises(NotImplementedError):
            self.workflow.emit_results(None, None, None, None)

    def test_append_path(self):
        self.workflow.append_to_path('input_dir', 'test')
        self.assertEqual(os.path.join(my_dir, "../../data/dream4", 'test'), self.workflow.input_dir)
        self.workflow.input_dir = None
        with self.assertRaises(ValueError):
            self.workflow.append_to_path('input_dir', 'test')

    def test_make_fake_metadata(self):
        self.workflow.meta_data_file = None
        self.workflow.read_metadata(file=None)
        self.assertEqual(self.workflow.meta_data.shape, (421, 4))

    def test_workflow_cv_priors_genes(self):
        self.workflow.split_gold_standard_for_crossvalidation = True
        self.workflow.cv_split_ratio = 0.5
        self.workflow.cv_split_axis = 0
        self.workflow.process_priors_and_gold_standard()
        self.assertEqual(self.workflow.priors_data.shape, (50, 100))
        self.assertEqual(self.workflow.gold_standard.shape, (50, 100))
        self.assertListEqual(self.workflow.priors_data.columns.tolist(), self.workflow.gold_standard.columns.tolist())
        self.workflow.align_priors_and_expression()
        self.assertEqual(self.workflow.priors_data.shape, (100, 100))
        self.assertEqual(self.workflow.gold_standard.shape, (50, 100))

    def test_workflow_cv_priors_tfs(self):
        self.workflow.split_gold_standard_for_crossvalidation = True
        self.workflow.cv_split_ratio = 0.5
        self.workflow.cv_split_axis = 1
        self.workflow.process_priors_and_gold_standard()
        self.assertEqual(self.workflow.priors_data.shape, (100, 50))
        self.assertEqual(self.workflow.gold_standard.shape, (100, 50))
        self.assertListEqual(self.workflow.priors_data.index.tolist(), self.workflow.gold_standard.index.tolist())
        self.workflow.align_priors_and_expression()
        self.assertEqual(self.workflow.priors_data.shape, (100, 50))
        self.assertEqual(self.workflow.gold_standard.shape, (100, 50))

    def test_workflow_cv_priors_flat(self):
        self.workflow.split_gold_standard_for_crossvalidation = True
        self.workflow.cv_split_ratio = 0.5
        self.workflow.cv_split_axis = None
        self.workflow.process_priors_and_gold_standard()
        self.assertEqual(self.workflow.priors_data.shape, (100, 100))
        self.workflow.align_priors_and_expression()
        self.assertEqual(self.workflow.priors_data.shape, (100, 100))

    def test_workflow_priors_filter(self):
        self.workflow.split_gold_standard_for_crossvalidation = True
        self.workflow.cv_split_ratio = 0.5
        self.workflow.cv_split_axis = 0
        self.workflow.tf_names = list(map(lambda x: "G" + str(x), list(range(1, 21))))
        self.workflow.gene_metadata = pd.DataFrame({"genes": list(map(lambda x: "G" + str(x), list(range(1, 51))))})
        self.workflow.gene_list_index = "genes"
        self.workflow.process_priors_and_gold_standard()

        self.assertEqual(self.workflow.gold_standard.shape, (50, 100))
        self.assertListEqual(self.workflow.priors_data.columns.tolist(), self.workflow.tf_names)

        self.workflow.align_priors_and_expression()
        self.assertEqual(self.workflow.priors_data.shape, (50, 20))
        self.assertEqual(self.workflow.expression_matrix.shape, (50, 421))
        self.assertListEqual(self.workflow.priors_data.index.tolist(), self.workflow.expression_matrix.index.tolist())

    def test_get_bootstraps(self):
        bootstrap_0 = [37, 235, 396, 72, 255, 393, 203, 133, 335, 144, 129, 71, 237, 390, 281, 178, 276, 254, 357, 402,
                       395, 252, 156, 413, 398, 50, 68, 215, 241, 352, 86, 141, 393, 7, 319, 317, 22, 313, 1, 384, 316,
                       209, 264, 216, 141, 115, 121, 30, 71, 387, 405, 49, 313, 3, 280, 43, 76, 26, 308, 336, 109, 371,
                       297, 15, 64, 196, 25, 367, 226, 391, 282, 153, 104, 22, 265, 195, 126, 279, 381, 356, 155, 313,
                       83, 166, 136, 288, 418, 266, 279, 143, 239, 87, 281, 243, 348, 74, 190, 302, 416, 216, 151, 183,
                       321, 369, 333, 259, 384, 253, 262, 52, 2, 76, 149, 203, 263, 77, 200, 75, 332, 43, 20, 30, 36,
                       359, 263, 301, 57, 240, 210, 96, 269, 10, 279, 380, 337, 391, 377, 152, 202, 148, 416, 140, 193,
                       94, 60, 152, 338, 371, 353, 130, 220, 103, 354, 266, 182, 352, 338, 198, 194, 327, 176, 54, 15,
                       389, 401, 170, 20, 118, 278, 397, 114, 97, 181, 340, 10, 96, 183, 317, 56, 217, 405, 231, 96, 25,
                       398, 141, 212, 116, 299, 134, 205, 184, 399, 24, 137, 199, 309, 325, 420, 357, 248, 21, 296, 77,
                       219, 177, 369, 303, 45, 343, 144, 412, 234, 45, 372, 322, 302, 384, 413, 63, 331, 35, 33, 130,
                       83, 48, 310, 288, 253, 156, 55, 210, 287, 28, 222, 330, 136, 109, 99, 32, 8, 84, 50, 79, 169,
                       320, 108, 211, 24, 113, 276, 44, 271, 158, 398, 275, 251, 154, 235, 86, 391, 227, 53, 366, 243,
                       290, 100, 228, 288, 403, 280, 211, 229, 94, 166, 175, 231, 389, 79, 63, 369, 87, 416, 298, 202,
                       194, 216, 226, 158, 145, 324, 320, 188, 206, 145, 167, 163, 156, 150, 294, 169, 205, 326, 153,
                       230, 240, 48, 178, 300, 105, 182, 256, 342, 272, 275, 265, 112, 220, 51, 367, 138, 123, 324, 407,
                       270, 191, 21, 174, 380, 131, 344, 208, 54, 71, 14, 205, 143, 409, 309, 212, 114, 238, 413, 44,
                       37, 150, 332, 12, 376, 315, 410, 215, 125, 43, 370, 294, 91, 112, 253, 325, 226, 417, 171, 410,
                       184, 73, 308, 89, 27, 43, 1, 338, 127, 94, 410, 340, 30, 359, 64, 150, 98, 308, 131, 70, 140,
                       295, 230, 83, 239, 176, 317, 269, 164, 279, 406, 122, 249, 351, 53, 393, 169, 344, 365, 246, 221,
                       244, 204, 338, 362, 395, 105, 36, 112, 144, 158, 115, 106, 212, 291, 337, 258]

        self.workflow.response = self.workflow.expression_matrix
        self.workflow.random_seed = 1
        self.workflow.num_bootstraps = 5
        bootstraps = self.workflow.get_bootstraps()
        self.assertEqual(len(bootstraps), 5)
        self.assertListEqual(bootstraps[0], bootstrap_0)

    def test_is_master(self):
        self.assertTrue(self.workflow.is_master())

    def test_make_output_dir(self):
        temp_dir = tempfile.mkdtemp()
        self.workflow.input_dir = temp_dir
        self.workflow.create_output_dir()
        self.assertTrue(os.path.exists(self.workflow.output_dir))
        os.rmdir(self.workflow.output_dir)
        os.rmdir(temp_dir)

    def test_shuffle_prior_labels(self):
        self.workflow.shuffle_prior_axis = 0
        np.testing.assert_array_almost_equal_nulp(self.workflow.priors_data.values, self.workflow.gold_standard.values)
        self.workflow.process_priors_and_gold_standard()
        self.assertTrue(all(self.workflow.priors_data.columns == self.workflow.gold_standard.columns))
        self.assertTrue(all(self.workflow.priors_data.index == self.workflow.gold_standard.index))
        self.assertTrue(all(self.workflow.priors_data.sum(axis=0) == self.workflow.gold_standard.sum(axis=0)))
        with self.assertRaises(AssertionError):
            np.testing.assert_array_almost_equal_nulp(self.workflow.priors_data.values,
                                                      self.workflow.gold_standard.values)

    def test_shuffle_prior_labels_2(self):
        self.workflow.shuffle_prior_axis = 1
        np.testing.assert_array_almost_equal_nulp(self.workflow.priors_data.values, self.workflow.gold_standard.values)
        self.workflow.process_priors_and_gold_standard()
        self.assertTrue(all(self.workflow.priors_data.columns == self.workflow.gold_standard.columns))
        self.assertTrue(all(self.workflow.priors_data.index == self.workflow.gold_standard.index))
        self.assertTrue(all(self.workflow.priors_data.sum(axis=1) == self.workflow.gold_standard.sum(axis=1)))
        with self.assertRaises(AssertionError):
            np.testing.assert_array_almost_equal_nulp(self.workflow.priors_data.values,
                                                      self.workflow.gold_standard.values)


class TestWorkflowFactory(unittest.TestCase):

    def test_base(self):
        worker = workflow.inferelator_workflow(regression=None, workflow=workflow.WorkflowBase)
        with self.assertRaises(NotImplementedError):
            worker.run()

    def test_bbsr(self):
        from inferelator.regression.bbsr_python import BBSRRegressionWorkflow
        worker = workflow.inferelator_workflow(regression="bbsr", workflow=workflow.WorkflowBase)
        self.assertTrue(isinstance(worker, BBSRRegressionWorkflow))

    def test_elasticnet(self):
        from inferelator.regression.elasticnet_python import ElasticNetWorkflow
        worker = workflow.inferelator_workflow(regression="elasticnet", workflow=workflow.WorkflowBase)
        self.assertTrue(isinstance(worker, ElasticNetWorkflow))

    def test_amusr(self):
        from inferelator.regression.amusr_regression import AMUSRRegressionWorkflow
        from inferelator.amusr_workflow import MultitaskLearningWorkflow
        worker = workflow.inferelator_workflow(regression="amusr", workflow="amusr")
        self.assertTrue(isinstance(worker, AMUSRRegressionWorkflow))
        self.assertTrue(isinstance(worker, MultitaskLearningWorkflow))

    def test_bad_inputs(self):
        with self.assertRaises(ValueError):
            worker = workflow.inferelator_workflow(regression="restlne", workflow=workflow.WorkflowBase)
        with self.assertRaises(ValueError):
            worker = workflow.inferelator_workflow(regression=1, workflow=workflow.WorkflowBase)
        with self.assertRaises(ValueError):
            worker = workflow.inferelator_workflow(regression=RegressionWorkflow, workflow="restlne")
        with self.assertRaises(ValueError):
            worker = workflow.inferelator_workflow(regression=RegressionWorkflow, workflow=None)
        with self.assertRaises(ValueError):
            worker = workflow.inferelator_workflow(regression=RegressionWorkflow, workflow=1)

    def test_tfa(self):
        from inferelator.tfa_workflow import TFAWorkFlow
        worker = workflow.inferelator_workflow(regression=RegressionWorkflow, workflow="tfa")
        self.assertTrue(isinstance(worker, TFAWorkFlow))

    def test_singlecell(self):
        from inferelator.single_cell_workflow import SingleCellWorkflow
        worker = workflow.inferelator_workflow(regression=RegressionWorkflow, workflow="single-cell")
        self.assertTrue(isinstance(worker, SingleCellWorkflow))
