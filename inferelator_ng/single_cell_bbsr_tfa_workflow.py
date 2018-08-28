from inferelator_ng import bbsr_tfa_workflow, bbsr_python, utils, single_cell, tfa, mi
import gc
import sys
import time
import pandas as pd
import numpy as np

KVS_CLUSTER_KEY = 'cluster_idx'

class Single_Cell_BBSR_TFA_Workflow(bbsr_tfa_workflow.BBSR_TFA_Workflow):
    cluster_index = None
    count_file_compression = None

    def compute_common_data(self):
        """
        Compute common data structures like design and response matrices.
        """
        self.filter_expression_and_priors()

        # Run the clustering once and distribute it to avoid a nasty spike in memory usage
        if self.is_master():
            self.cluster_index = single_cell.initial_clustering(self.expression_matrix)
            self.kvs.put(KVS_CLUSTER_KEY, self.cluster_index)
        else:
            self.cluster_index = self.kvs.get(KVS_CLUSTER_KEY)
        utils.kvs_sync_processes(self.kvs, self.rank)
        utils.kvsTearDown(self.kvs, self.rank, kvs_key=KVS_CLUSTER_KEY)

    def compute_activity(self):
        # Bulk up and normalize clusters
        bulk = single_cell.make_clusters_from_singles(self.expression_matrix, self.cluster_index, pseudocount=True)
        utils.Debug.vprint("Pseudobulk data matrix assembled [{}]".format(bulk.shape))

        # Calculate TFA and then break it back into single cells
        self.design = tfa.TFA(self.priors_data, bulk, bulk).compute_transcription_factor_activity()
        self.design = single_cell.make_singles_from_clusters(self.design, self.cluster_index,
                                                             columns=self.expression_matrix.columns)
        self.response = self.expression_matrix

    def run_bootstrap(self, bootstrap):
        utils.Debug.vprint('Calculating MI, Background MI, and CLR Matrix', level=1)

        X = self.design.iloc[:, bootstrap]
        Y = self.response.iloc[:, bootstrap]
        boot_cluster_idx = self.cluster_index[bootstrap]

        X_bulk = single_cell.make_clusters_from_singles(X, boot_cluster_idx)
        Y_bulk = single_cell.make_clusters_from_singles(Y, boot_cluster_idx)

        utils.Debug.vprint("Rebulked design {des} & response {res} data".format(des=X_bulk.shape, res=Y_bulk.shape))

        # Calculate CLR & MI if we're proc 0 or get CLR & MI from the KVS if we're not
        clr_mat, mi_mat = mi.MIDriver(kvs=self.kvs, rank=self.rank).run(X_bulk, Y_bulk)

        # Trying to get ahead of this memory fire
        X_bulk = Y_bulk = bootstrap = boot_cluster_idx = mi_mat = None
        gc.collect()

        utils.Debug.vprint('Calculating betas using BBSR', level=1)
        ownCheck = utils.ownCheck(self.kvs, self.rank, chunk=25)

        # Run the BBSR on this bootstrap
        betas, re_betas = bbsr_python.BBSR_runner().run(X, Y, clr_mat, self.priors_data, self.kvs, self.rank, ownCheck)

        # Trying to get ahead of this memory fire
        X = Y = clr_mat = None
        gc.collect()

        return betas, re_betas

    def read_expression(self):
        """
        Overload the workflow.workflowBase expression reader to force count data in as uint16
        """
        file_name = self.input_path(self.expression_matrix_file)
        st = time.time()
        utils.Debug.vprint("Reading {f} file data".format(f=file_name))

        # Read in the count file as a pandas dataframe
        self.expression_matrix = pd.read_csv(file_name, sep="\t", header=0, index_col=0,
                                             compression=self.count_file_compression)

        # Downcast to save on memory
        self.expression_matrix = self.expression_matrix.apply(pd.to_numeric, downcast='unsigned')

        et = int(time.time() - st)
        df_shape = self.expression_matrix.shape
        df_size = int(sys.getsizeof(self.expression_matrix)/1000000)
        utils.Debug.vprint("Proc {r}: Single-cell data {s} read into memory ({m} MB in {t} sec)".format(r=self.rank,
                                                                                                        s=df_shape,
                                                                                                        m=df_size,
                                                                                                        t=et))
