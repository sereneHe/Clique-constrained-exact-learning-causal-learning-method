# To run, type:
# python3 evaluate_scores.py [graph_file_name] [sample_file_name] [data_directory]
# It reads and writes files in '../Instances/data/'

#from test_latent_scores import generate_scores_bidirect,generate_scores_bidirect_m3hc
import numpy as np
import sys
from generate_samples import read_graph_from_file
from utils import find_c_components
import networkx as nx
from utils import compute_BiC_c_comps_sets


def dfs(B, node, visited, temp_group):
        visited[node] = True
        temp_group.append(node)
        for j in range(len(B[node])):
                if j != node and visited[j] == False and B[node][j] == 1:
                        temp_group = dfs(B, j, visited, temp_group)
        return temp_group


def get_districts(B):
        nnodes = len(B)
        visited = [False for i in range(nnodes)]
        node_groups = []
        for node in range(nnodes):
                if visited[node] == False:
                        temp_group = []
                        node_groups.append(dfs(B, node, visited, temp_group))

        inbidir = [False for i in range(nnodes)]
        for i in range(len(node_groups)):
#                nodes_sorted = []
#                for node in range(nnodes):
#                        if node in node_groups[i]:
#                                nodes_sorted.append(node)
                if len(node_groups[i]) > 1:
                        node_groups[i].sort()
                        for node in node_groups[i]:
                                inbidir[node] = True

        # add all single node districts
        districts = []
        for i in range(nnodes):
                if inbidir[i] == False:
                        #newdist = tuple(i)
                        districts.append(((i,), ()))

        # add all districts with bidirected edges
        for i in range(len(node_groups)):
                if len(node_groups[i]) > 1:
                        newnodes = tuple(node_groups[i])
                        newedges = []
                        for j in range(len(node_groups[i])-1):
                                for k in range(j+1, len(node_groups[i])):
                                        if B[node_groups[i][j]][node_groups[i][k]] == 1:
                                                newedges.append((node_groups[i][j], node_groups[i][k]))
                        newedges = tuple(newedges)
                        districts.append((newnodes, newedges))
                
        return districts

def get_parents(D, districts):
        nnodes = len(D)
        ind_district = [None for i in range(nnodes)] # stores index of district where each node exists
        ind_parent = [None for i in range(nnodes)] # stores index of parent set inside district where each node exists
        for i in range(len(districts)):
                for j in range(len(districts[i][0])):
                        node = districts[i][0][j]
                        ind_district[node] = i
                        ind_parent[node] = j

        parents = [[] for i in range(len(districts))]
        for i in range(len(districts)):
                parents[i] = [[] for j in range(len(districts[i][0]))]

        for i in range(nnodes):
                for j in range(nnodes):
                        if D[i][j] == 1:
                                parents[ind_district[j]][ind_parent[j]].append(i)

        for i in range(len(parents)):
                for j in range(len(parents[i])):
                        parents[i][j] = tuple(parents[i][j])
                parents[i] = tuple(parents[i])

        return parents

def main():
        data_directory = '../Instances/data/'
        graph_filename = 'graph_bhattacharya_fig1c.txt'
        sample_filename = 'sample_bhattacharya_fig1c.txt'
        
        if len(sys.argv) > 1:
                graph_filename = sys.argv[1]
        if len(sys.argv) > 2:
                sample_filename = sys.argv[2]
        if len(sys.argv) > 3:
                data_directory = sys.argv[3]

        graph_filename = data_directory + graph_filename
        sample_filename = data_directory + sample_filename
        
        graph = read_graph_from_file(graph_filename)

        with open(sample_filename, 'rb') as f:
	        data = np.loadtxt(f, skiprows=0)

        D = graph[0]
        B = graph[1]
        districts = get_districts(B)
        parents = get_parents(D, districts)

        total_score = 0.0
        for i in range(len(districts)):
                score = compute_BiC_c_comps_sets(data,districts[i][0],parents[i],districts[i][1])
                total_score += score
                print(str(districts[i])+': '+str(parents[i])+', score: '+str(score))

        print('Score: '+str(total_score))
        

if __name__ == "__main__":

    main()
