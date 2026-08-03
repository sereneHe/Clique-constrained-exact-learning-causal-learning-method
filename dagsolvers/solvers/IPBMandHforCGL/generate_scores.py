# To run, type:
# python3 generate_scores.py sample_file_name [c_size] [single_parent_size] [other_c_parent_size] [data_directory]
# It reads and writes files in '../Instances/data/'

from test_latent_scores import generate_scores_bidirect,generate_scores_bidirect_m3hc
import numpy as np
import sys




def main():
        data_directory = '../Instances/data/'
        #datasets = ['example.txt']
        datasets = ['sample_bhattacharya_fig1c.txt']

        c_size = 3 #1 #3
        single_parent_size = 1 #2 #3
        other_c_parent_size = 1

        if len(sys.argv) > 1:
                datasets = [sys.argv[1]]
        if len(sys.argv) > 2:
                c_size = int(sys.argv[2])
        if len(sys.argv) > 3:
                single_parent_size = int(sys.argv[3])
        if len(sys.argv) > 4:
                other_c_parent_size = int(sys.argv[4])
        if len(sys.argv) > 5:
                data_directory = sys.argv[5]


        for dataset in datasets:

	        with open(data_directory + dataset, 'rb') as f:
	                data = np.loadtxt(f, skiprows=0)

	        # visible
	        observed_data = data


                #	file_name = data_directory + 'score_' + dataset[:-4] + '.pkl'
	        file_name = data_directory + 'score_' + dataset[:-4] + '-cs' + str(c_size) + '_sps' + str(single_parent_size) + '_ocps' + str(other_c_parent_size) + '.pkl'
	        print(file_name)


	        generate_scores_bidirect(observed_data,
	                                 single_c_parent_size = single_parent_size,
	                                 other_c_parent_size = other_c_parent_size,
	                                 c_size = c_size,
	                                 file_name = file_name)


if __name__ == "__main__":

    main()
