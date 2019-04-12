import csv
from itertools import islice
import helpers 
import json
import numpy as np
import time
from itertools import tee
import os
import sys
import h5py


class PrepareTrainingFramesHdf5():
    def __init__(self,data,param,toy,smooth):
        data = json.load(open(data))
        param = json.load(open(param))
        self.frames_temp = data["temp"] + "frames.txt"
        self.trajectories_temp = data["temp"] + "trajectories.txt"
        self.framerate = 1./float(param["framerate"])

        self.original_file = data["preprocessed_datasets"] + "{}.csv"

        self.smooth = smooth
        self.smooth_suffix = param["smooth_suffix"]

        if toy:
            self.hdf5_dest = data["hdf5_toy"]
        else:
            self.hdf5_dest = data["hdf5_file"]

        with h5py.File(self.hdf5_dest,"a") as f: 
            if "frames" not in f:
                print("in1")
                f.create_group("frames")

        self.shift = int(param["shift"])
        self.t_obs = int(param["t_obs"])
        self.t_pred = int(param["t_pred"])
        self.padding = param["padding"]
        self.types_dic = param["types_dic"]





    """
        parameters: dict containing reauired parameters[
            "original_file" path for file containing the original data
            "frames_temp"   path to store temporarily the frame-shaped data extracted from original_file
            "trajectories_temp" path to store temporarily the trajectory-shaped data extracted from original_file
            "shift" the size of the step between two feature extraction for the main trajectory
            t_obs: number of observed frames
            t_pred: number of frames to predict
            "scene" scene name
            "framerate" framerate of the original data
            "data_path path for file where to write down features
            "label_path" path for file where to write down labels
        ]
    """
    def extract_data(self,scene):

        



        max_neighbors = self.__nb_max_neighbors(scene)
        print("max_neighbors {}".format(max_neighbors))

        if self.smooth:
            smooth_params ={
                "framerate":self.framerate,
                "destination_path": self.original_file.format(scene+self.smooth_suffix)
            }
            helpers.save_trajs(self.trajectories_temp,self.original_file.format(scene),smooth_params,smooth = True)

            scene += self.smooth_suffix

        helpers.extract_frames(self.original_file.format(scene),self.frames_temp,save = True)
        
        with h5py.File(self.hdf5_dest,"r+") as f:
            # for key in f:
            #     print(key
            group = f["frames"]
            dset = None
            dset_types = None

            data_shape = (max_neighbors,self.t_obs + self.t_pred,2)

            if scene in group:
                del group[scene] 
            if scene+"_types" in group:                
                del group[scene+"_types"] 

            dset = group.create_dataset(scene,shape=(0,data_shape[0],data_shape[1],data_shape[2]),maxshape = (None,data_shape[0],data_shape[1],data_shape[2]),dtype='float32')
            dset_types = group.create_dataset(scene+"_types",shape=(0,data_shape[0]),maxshape = (None,data_shape[0]),dtype='float32')

            with open(self.frames_temp) as frames:
                observations = {}
                sample_id = 0
                for frame in frames:
                    delete_ids = []
                    observations[sample_id] = []
                    sample_id += 1

                    for id_ in observations:
                        if len(observations[id_]) < self.t_obs + self.t_pred:
                            observations[id_].append(frame)
                        else:
                            samples,types = self.__samples(observations[id_])
                            samples,types = np.array(samples),np.array(types)

                            nb_neighbors = len(samples)
                            if nb_neighbors != 0:
                                padding = np.zeros(shape = (max_neighbors-nb_neighbors,data_shape[1],data_shape[2]))
                                samples = np.concatenate((samples,padding),axis = 0)

                                padding_types = np.zeros(shape = (max_neighbors-nb_neighbors))
                                types = np.concatenate((types,padding_types),axis = 0)

                                dset.resize(dset.shape[0]+1,axis=0)
                                dset[-1] = samples

                                dset_types.resize(dset_types.shape[0]+1,axis=0)
                                dset_types[-1] = types

                            
                            
                            delete_ids.append(id_)
                    for id_ in delete_ids:
                        del observations[id_]
        helpers.remove_file(self.frames_temp)
        if self.smooth:
            helpers.remove_file(self.original_file.format(scene))

    """
    in:
        observations: list of frames size t_obs+t_pred
        t_obs: number of observed frames
        t_pred: number of frames to predict
        
    out:
        features: for the list of t_obs+t_pred frames, for each id in the sequence
        if its coordinates are not all [-1,-1] during observation time, its coordinates
        during observation time are flattened and added
        
        labels: same idea but for prediction time
    """
    def __samples(self,observations):
        ids,types = self.__get_neighbors(observations)
        samples = []
        types_list = []
        for id_ in sorted(ids):
            if self.__add_neighbor(ids,id_,0):
                sample = ids[id_][0:self.t_obs+self.t_pred]
                samples.append(sample)
                types_list.append(types[id_])
        return samples,types_list

   


    """
        in: 
            start:frame number where the trajectory begins
            stop: frame number where the trajectory stops
            frames_path: path to the file containing frames
        out:
            returns ids but the lists are filled with the coordinates
            of theirs objects for a given frame or [-1,-1] if its not in 
            the given frame
    """
    def __get_neighbors(self,frames):
        ids = {}
        types = {}
        for i,frame in enumerate(frames):
            frame = json.loads(frame)
            frame = frame["ids"]

            # if id in frame and not yet appeared in the sequence
            # add the id to observed ids and add padding point from
            # t0 up to  t - 1
            for id_ in frame:
                if id_ != "frame":
                    if int(id_) not in ids:
                        ids[int(id_)] = [[self.padding,self.padding] for j in range(i)]
                    if int(id_) not in types:
                        types[int(id_)] = self.types_dic[frame[str(id_)]["type"]]
                       
            
            # for every already observed ids if its in the current frame, add its 
            # coordinates otherwise add padding
            for id_ in ids:
                if str(id_) in frame:
                    ids[id_].append(frame[str(id_)]["coordinates"])
                else:
                    ids[id_].append([self.padding,self.padding])
        return ids,types



    """
        in:
            t_obs: number of observed frames
            ids: ids  filled with the coordinates
            id_: id of the neighbor to test
            of theirs objects for a given frame or [-1,-1] if its not in 
            the given frame
            current_frame: the frame of the trajectory to be considered
        out: 
            True if the neighboor appears during observation time
            *** if appears at least in the last obervation timestep ***
    """
    # def __add_neighbor(self,ids,id_,current_frame):
    #     add = False
    #     for p in ids[id_][current_frame:current_frame+self.t_obs]:
    #         if p != [self.padding,self.padding]:
    #             return True
    #     return add

    def __add_neighbor(self,ids,id_,current_frame):
        if ids[id_][current_frame:current_frame+self.t_obs][-1] != [self.padding,self.padding]:
            return True
        return False



    def __nb_max_neighbors(self,scene):
        helpers.extract_frames(self.original_file.format(scene),self.frames_temp,save = True)
        nb_agents_scene = []

        with open(self.frames_temp) as frames:
            for i,frame in enumerate(frames):
                # print(frame["ids"])
                frame = json.loads(frame)
                nb_agents = len(frame["ids"].keys())
                nb_agents_scene.append(nb_agents)
        os.remove(self.frames_temp)
        return np.max(nb_agents_scene)


# python prepare_training/prepare_training.py parameters/data.json parameters/prepare_training.json lankershim_inter2


def main():

    args = sys.argv
    prepare_training = PrepareTrainingFramesHdf5(args[1],args[2])
    
    
    s = time.time()
    prepare_training.extract_data(args[3])               
    print(time.time()-s)


                    
if __name__ == "__main__":
    main()