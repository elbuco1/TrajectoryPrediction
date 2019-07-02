import torch
from torch.utils import data
from classes.pretrained_vgg import customCNN1

import cv2
import numpy as np 
import json
import h5py
import cv2
import time
import helpers
from joblib import load
import sys
from PIL import Image
from torchvision import transforms

class CustomDataLoader():
      def __init__(self,batch_size,shuffle,drop_last,dataset,test = 0):
            self.shuffle = shuffle 
            self.dataset = dataset
            # print("len")
            self.data_len = self.dataset.get_len()
            # print(self.data_len)

            self.batch_size = batch_size
            self.drop_last = drop_last
            # self.batches = self.__split_batches
            # self.batch_idx = 0
            self.test = test
            self.split_batches()
            

            # print(self.batches[:3])
      def split_batches(self):
            self.batches = list(torch.utils.data.BatchSampler(
                  torch.utils.data.RandomSampler(range(self.data_len)),
                  batch_size = self.batch_size,
                  drop_last =self.drop_last))
            self.batch_idx = 0
            self.nb_batches = len(self.batches)
            print(self.nb_batches)
            if self.test :
                  self.nb_batches = 30

            

      def __iter__(self):
            return self
      def __next__(self):

            if self.batch_idx >= self.nb_batches:
                  self.split_batches()
                  raise StopIteration
            else:     
                  ids = sorted(self.batches[self.batch_idx])
                  self.batch_idx += 1 
                  return self.dataset.get_ids(ids)



"""
      set_type:  train eval  test train_eval
      use_images: True False
      use_neighbors: True False
      predict_offsets: 0: none, 1: based on last obs point, 2: based on previous point

      data_type: frames trajectories
"""
class Hdf5Dataset():
      'Characterizes a dataset for PyTorch'
      def __init__(self,padding,images_path,hdf5_file,scene_list,t_obs,t_pred,set_type,
                  normalize,use_images,data_type,use_neighbors,augmentation,
                  augmentation_angles,centers,use_masks = False,reduce_batches = True,
                  predict_offsets = 0,offsets_input = 0,predict_smooth=0,smooth_suffix = "",evaluation = 0):

            self.images_path = images_path + "{}.jpg"
            
            self.set_type = set_type
            self.scene_list = scene_list

            self.data_type = data_type
            self.use_images = use_images
            self.use_neighbors = use_neighbors
            self.use_masks = use_masks

            self.evaluation = evaluation

            
            self.centers = centers
            self.reduce_batches = reduce_batches
            self.predict_offsets = predict_offsets
            self.offsets_input = offsets_input

            self.predict_smooth = predict_smooth
            # self.smooth_suffix = smooth_suffix
            self.normalize = normalize

            self.hdf5_file = h5py.File(hdf5_file,"r")

            if self.evaluation:
                  self.dset_name = self.scene_list[0]
                  self.dset_types = "{}_types".format(self.scene_list[0])
                  self.coord_dset = self.hdf5_file[self.data_type][self.dset_name]
                  self.types_dset = self.hdf5_file[self.data_type][self.dset_types]  

            else: 
                  self.dset_name = "samples_{}_{}".format(set_type,data_type)
                  self.dset_img_name = "images_{}_{}".format(set_type,data_type)
                  self.dset_types = "types_{}_{}".format(set_type,data_type)   
                  self.coord_dset = self.hdf5_file[self.dset_name]            
                  self.scenes_dset = self.hdf5_file[self.dset_img_name]   
                  self.types_dset = self.hdf5_file[self.dset_types]  




            self.t_obs = t_obs
            self.t_pred = t_pred
            self.seq_len = t_obs + t_pred
            self.augmentation = augmentation 
            self.augmentation_angles = augmentation_angles
            self.padding = padding
            

            if self.augmentation:
                  self.r_matrices = self.__get_matrices()
                  self.scene_list = helpers.helpers_training.augment_scene_list(self.scene_list,self.augmentation_angles)
            if self.use_images:
                  self.images = self.__load_images()
            # self.scaler = load("./data/scalers/scaler.joblib")
            self.scaler = json.load(open("./data/scalers/scaler.json"))

            # self.hdf5_file = hdf5_file
            

            self.shape = self.coord_dset.shape
            
      def __del__(self):
            self.hdf5_file.close()
            print("closed")
      # def get_len(self):
      #       with h5py.File(self.hdf5_file,"r") as hdf5_file: 
      #             if self.augmentation:
      #                   return hdf5_file[self.dset_name].shape[0]  * (len(self.augmentation_angles) + 1)
      #             return hdf5_file[self.dset_name].shape[0]
      def get_len(self):
            
            if self.augmentation:
                  return self.shape[0]  * (len(self.augmentation_angles) + 1)
            return self.shape[0]

      


      def get_ids(self,ids):
            torch.cuda.synchronize()
            s = time.time()

            types,m_ids,X,y,seq = [],[],[],[],[]
            max_batch = self.coord_dset.shape[1]

            if self.augmentation:
                  ids,m_ids = self.__augmentation_ids(ids)   

            scenes = [self.scene_list[0] for _ in range(len(ids))]
            if not self.evaluation:                             
                  scenes = [img.decode('UTF-8') for img in self.scenes_dset[ids]] # B

            
            # load sequence once and for all to limit hdf5 access
            # if self.predict_smooth:
            #       X = self.coord_dset[ids,:,:self.t_obs]
            #       y = self.coord_dset_smooth[ids,:,self.t_obs:self.seq_len]   
            #       seq = np.concatenate([X,y],axis = 2)              

            # else:
            seq = self.coord_dset[ids]
            X = seq[:,:,:self.t_obs]
            y = seq[:,:,self.t_obs:self.seq_len]

            # compute max nb of agents in a frame
            if self.reduce_batches:
                  max_batch = self.__get_batch_max_neighbors(X)

            X = X[:,:max_batch]
            y = y[:,:max_batch]
            seq = seq[:,:max_batch]

            if self.use_neighbors:
                  types = self.types_dset[ids,:max_batch] #B,N,tpred,2
            else:
                  types =  self.types_dset[ids,0] #B,1,tpred,2
                  


            points_mask = []
            if self.use_neighbors:
                  X,y,points_mask,y_last,X_last = self.__get_x_y_neighbors(X,y,seq)


            else:       
                  X,y,points_mask,y_last,X_last = self.__get_x_y(X,y,seq)                      


            sample_sum = (np.sum(points_mask[1].reshape(points_mask[1].shape[0],points_mask[1].shape[1],-1), axis = 2) > 0).astype(int)
            active_mask = np.argwhere(sample_sum.flatten()).flatten()


            if self.augmentation:
                  X,y = self.__augment_batch(scenes,X,y,m_ids)
                  scenes = [scene if m == 0 else scene +"_{}".format(m) for scene,m in zip(scenes,m_ids)] # B


            if self.normalize:
                  x_shape = X.shape 
                  y_shape = y.shape 

                  if self.offsets_input:
                        # print("need to implment normalisation for offsets inputs")
                        meanx =  self.scaler["standardization"]["meanx"]
                        meany =  self.scaler["standardization"]["meany"]
                        stdx =  self.scaler["standardization"]["stdx"]
                        stdy =  self.scaler["standardization"]["stdy"]

                        X[:,:,:,0] = helpers.helpers_training.standardization(X[:,:,:,0],meanx,stdx)
                        X[:,:,:,1] = helpers.helpers_training.standardization(X[:,:,:,1],meany,stdy)
                        


                  else:
                        
                        min_ =  self.scaler["normalization"]["min"]
                        max_ =  self.scaler["normalization"]["max"]
                        X = helpers.helpers_training.min_max_scale(X,min_,max_)

            





            out = [
                  torch.FloatTensor(X).contiguous(),
                  torch.FloatTensor(y).contiguous(),
                  torch.FloatTensor(types)
            ]   

            

            if self.use_masks:
                  out.append(points_mask)
                  out.append(torch.LongTensor(active_mask))
            
            imgs = torch.FloatTensor([])
            if self.use_images:
                  imgs = torch.stack([self.images[img] for img in scenes],dim = 0) 
            out.append(imgs)
            out.append(y_last)
            out.append(X_last)

      
            # print("data loading {}".format(time.time()-s))
            return tuple(out)


      def __get_batch_max_neighbors(self,X):
           
            active_mask = (X == self.padding).astype(int)
            a = np.sum(active_mask,axis = 3)
            b = np.sum( a, axis = 2)
            nb_padding_traj = b/float(2.0*self.t_obs) #prop of padded points per traj
            active_traj = nb_padding_traj < 1.0 # if less than 100% of the points are padding points then its an active trajectory
            nb_agents = np.sum(active_traj.astype(int),axis = 1)                      
            max_batch = np.max(nb_agents)

            return max_batch

           

           


      # def __get_x_y_neighbors(self,coord_dset,ids,max_batch,types_dset,hdf5_file):
      def __get_x_y_neighbors(self,X,y,seq):
            active_mask = (y != self.padding).astype(int)    
            active_mask_in = (X != self.padding).astype(int)            
            active_last_points = []
            original_x = []

            if self.predict_offsets:
                  if self.predict_offsets == 1:
                        # offsets according to last obs point, take last point for each obs traj and make it an array of dimension y
                        last_points = np.repeat(  np.expand_dims(X[:,:,-1],2),  self.t_pred, axis=2)#B,N,tpred,2
                  elif self.predict_offsets == 2:# y shifted left

                        # offsets according to preceding point point, take points for tpred shifted 1 timestep left
                        last_points = seq[:,:,self.t_obs-1:self.seq_len-1]


                  
                  active_last_points = np.multiply(active_mask,last_points)
                  y = np.subtract(y,active_last_points)
            if self.offsets_input:
                  first_points = np.concatenate([np.expand_dims(X[:,:,0],2), X[:,:,0:self.t_obs-1]], axis = 2)
                  active_first_points = np.multiply(active_mask_in,first_points)
                  original_x = X
                  original_x = np.multiply(original_x,active_mask_in) # put padding to 0

                  
                  X = np.subtract(X,active_first_points)


            y = np.multiply(y,active_mask) # put padding to 0
            X = np.multiply(X,active_mask_in) # put padding to 0
            
            return X,y,(active_mask_in,active_mask),active_last_points,original_x 

      # def __get_x_y(self,coord_dset,ids,max_batch,types_dset,hdf5_file):
      def __get_x_y(self,X,y,seq):

            X = np.expand_dims( X[:,0] ,1) # keep only first neighbors and expand nb_agent dim 
            y = np.expand_dims( y[:,0], 1) #B,1,tpred,2 # keep only first neighbors and expand nb_agent dim 
            seq = np.expand_dims( seq[:,0], 1) #B,1,tpred,2 # keep only first neighbors and expand nb_agent dim 
            
            active_last_points = []
            original_x = []

            
            active_mask = (y != self.padding).astype(int)
            active_mask_in = (X != self.padding).astype(int)            

            if self.predict_offsets:

                  if self.predict_offsets == 1 :
                        # last_points = np.repeat(  np.expand_dims(np.expand_dims(X,1)[:,:,-1],2),  self.t_pred, axis=2) #B,1,tpred,2
                        last_points = np.repeat(  np.expand_dims(X[:,:,-1],2),  self.t_pred, axis=2) #B,1,tpred,2
                  
                  elif self.predict_offsets == 2: # y shifted left
                        last_points = seq[:,:,self.t_obs-1:self.seq_len-1]
                        # last_points = np.expand_dims( a , 1)

                  active_last_points = np.multiply(active_mask,last_points)
                  y = np.subtract(y,active_last_points)

            if self.offsets_input:
                  # first_points = seq[:,:,0:self.t_obs]
                  # concatenate the first point of X to X in order to get as many offsets as position
                  first_points = np.concatenate([np.expand_dims(X[:,:,0],2), X[:,:,0:self.t_obs-1]], axis = 2)

                  # apply active mask of input points
                  active_first_points = np.multiply(active_mask_in,first_points)

                  # keep original inputs
                  original_x = X
                  # apply the input active mask on the original inputs to remove the padding
                  original_x = np.multiply(original_x,active_mask_in) # put padding to 0

                  # subtract x shifted right to x in order to get offsets, offsets[0] = 0
                  X = np.subtract(X,active_first_points)
                  # X = np.repeat(X,)
                  # first_points = np.repeat(  np.expand_dims(X[:,:,0],2),  self.t_obs, axis=2)#B,N,tpred,2
                  # X = np.subtract(X,active_first_points)


            y = np.multiply(y,active_mask) # put padding to 0
            X = np.multiply(X,active_mask_in) # put padding to 0


            return X,y,(active_mask_in,active_mask),active_last_points,original_x

      def __augmentation_ids(self,ids):
            red_ids = sorted(np.array(ids) % self.shape[0])
            m_ids = (np.array(ids) / float(self.shape[0]) ).astype(int)*90
            ids,matrix_indexes = [],[]

            for i,j in zip(red_ids,m_ids):
                  if i not in ids:
                        ids.append(i)
                        matrix_indexes.append(j)

            # for i in range(len(red_ids)):                              
            #       if i > 0 and  red_ids[i] == ids[-1]:
            #             ids.append(red_ids[i]+1)
            #       else:
            #             ids.append(red_ids[i])
            return ids,matrix_indexes

      def __augment_batch(self,scenes,X,y,m_ids):
            centers = np.array([self.centers[scene] for scene in scenes]) # B,2
            centers = np.expand_dims(centers,axis = 1) # B,1,2
            centers = np.expand_dims(centers,axis = 1) # B,1,1,2
            centers = np.repeat(centers,X.shape[1],axis = 1) # B,N,1,2

            centers_x = np.repeat(centers,X.shape[2],axis = 2) # B,N,t_obs,2
            centers_y = np.repeat(centers,y.shape[2],axis = 2) # B,N,t_pred,2

            centers_x = np.multiply( (X != self.padding).astype(int), centers_x) # put 0 centers where padding points
            centers_y = np.multiply( (y != self.padding).astype(int), centers_y)

            matrices = np.array([self.r_matrices[m] for m in m_ids]) #B,2,2
            matrices = np.expand_dims(matrices,axis = 1) #B,1,2,2
            matrices = np.repeat(matrices,X.shape[1],axis = 1) #B,N,2,2

            matrices_x = np.repeat( np.expand_dims(matrices,axis = 2), X.shape[2],axis=2) #B,N,tobs,2,2
            matrices_y = np.repeat( np.expand_dims(matrices,axis = 2), y.shape[2],axis=2) #B,N,pred,2,2

            matrices_x = np.multiply( np.expand_dims((X != self.padding).astype(int),4), matrices_x) # put 0 matrices where padding points on x
            matrices_y = np.multiply( np.expand_dims( (y != self.padding).astype(int),4), matrices_y) # put 0 matrices where padding points on y


            eyes = np.expand_dims(np.expand_dims(np.expand_dims(np.eye(X.shape[-1]), 0),0),0) # create identity matrix of dimension 1,1,1,2,2
            eyes_x = eyes.repeat(X.shape[0],0).repeat(X.shape[1],1).repeat(X.shape[2],2) # B,N,tobs,2,2
            eyes_y = eyes.repeat(y.shape[0],0).repeat(y.shape[1],1).repeat(y.shape[2],2) # B,N,tpred,2,2

            eyes_x = np.multiply( np.expand_dims( (X == self.padding).astype(int) ,4), eyes_x) # put 0 matrices where normal points on x
            eyes_y = np.multiply( np.expand_dims( (y == self.padding).astype(int) ,4), eyes_y) # put 0 matrices where normal points on y

            matrices_x = np.add(matrices_x,eyes_x) # identity on padding points, rotation on normal points
            matrices_y = np.add(matrices_y,eyes_y)
           

            X = np.subtract(X,centers_x) # translate scene put origin on scene center
            X = np.matmul(X,matrices) # rotate
            X = np.add(X,centers_x) # translate back

            if not self.predict_offsets:
                  y = np.subtract(y,centers_y)
            y = np.matmul(y,matrices)

            if not self.predict_offsets:
                  y = np.add(y,centers_y)

            return X,y


      # def __load_images(self):
      #       images = {}
      #       for scene in self.scene_list:
      #             img = torch.FloatTensor(cv2.imread(self.images_path.format(scene)))
      #             img = img.permute(2,0,1)
      #             images[scene] = img
      #       return images

      def __load_images(self):#cuda
            images = {}
            print("loading images features")
            cnn = customCNN1()
            cnn.eval()
            cnn = cnn.cuda()
            paddings = self.__get_paddings()
            for scene,pad in zip(self.scene_list,paddings):
                  img = Image.open(self.images_path.format(scene))
                  transform = transforms.Compose([
                        transforms.Pad(pad),
                        transforms.ToTensor(),
                        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
                  ])

                  img = transform(img)
                  img = img.cuda()
                  print(img.size())
                  
                  img = img.unsqueeze(0)
                  img = cnn(img)
                  img = img.squeeze(0)

                  print(img.size())

                  img = img.cpu()
                  images[scene] = img
                  

            print("Done!")
            
            return images
      def __get_paddings(self):
            widths,heights = [],[]
            for scene in self.scene_list:
                  img = np.array(Image.open(self.images_path.format(scene)))
                  height,width,_ = img.shape
                  heights.append(height)
                  widths.append(width)
            max_height = np.max(heights)
            max_width = np.max(widths)
            
            paddings = []
            for scene in self.scene_list:
                  img = np.array(Image.open(self.images_path.format(scene)))
                  height,width,_ = img.shape
                  pad_height = max_height - height
                  pad_width = max_width  - width 

                  pad_height = self.__get_pad(pad_height)
                  pad_width = self.__get_pad(pad_width)
                  padding = (pad_width[0],pad_height[0],pad_width[1],pad_height[1])
                  paddings.append(padding)
            return paddings

      def __get_pad(self,v):
            if v % 2 == 0:
                  v = int(v/2)
                  return (v,v)
            else:
                  v = int(v/2)
                  return (v,v+1)

      def __get_matrices(self):

            matrices = {}

            for theta in [0] + self.augmentation_angles:
                  theta_rad = np.radians(theta)
                  c, s = np.cos(theta_rad), np.sin(theta_rad)
            
                  r = np.array([[c,-s],
                              [s,c]
                              ])
                  matrices[theta] = r 
            return matrices

