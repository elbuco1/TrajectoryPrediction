import torch
import time
import matplotlib.pyplot as plt
import torch
import torch.nn as nn
import numpy as np
from joblib import load
import matplotlib.cm as cm
import json
from classes.datasets import Hdf5Dataset,CustomDataLoader
from matplotlib.lines import Line2D
import random 


def load_data_loaders(data,prepare_param,training_param,net_params,data_file,scenes,batch_size):
    train_eval_scenes,train_scenes,test_scenes,eval_scenes = scenes

       
    if training_param["set_type_train"] == "train_eval":
        train_scenes = train_eval_scenes
    if training_param["set_type_test"] == "eval":
        test_scenes = eval_scenes
    


    train_dataset = Hdf5Dataset(
        images_path = data["prepared_images"],
        hdf5_file= data_file,
        scene_list= train_scenes,
        t_obs=prepare_param["t_obs"],
        t_pred=prepare_param["t_pred"],
        set_type = training_param["set_type_train"], # train
        use_images = net_params["use_images"],
        data_type = "trajectories",
        use_neighbors = net_params["use_neighbors"],
        use_masks = 1,
        predict_offsets = net_params["offsets"],
        offsets_input = net_params["offsets_input"],

        predict_smooth= training_param["predict_smooth"],
        smooth_suffix= prepare_param["smooth_suffix"],
        centers = json.load(open(data["scene_centers"])),
        padding = prepare_param["padding"],

        augmentation = training_param["augmentation"],
        augmentation_angles = training_param["augmentation_angles"],
        normalize =training_param["normalize"]
        )

    eval_dataset = Hdf5Dataset(
        images_path = data["prepared_images"],
        hdf5_file= data_file,
        scene_list= test_scenes, #eval_scenes
        t_obs=prepare_param["t_obs"],
        t_pred=prepare_param["t_pred"],
        set_type = training_param["set_type_test"], #eval
        use_images = net_params["use_images"],
        data_type = "trajectories",
        use_neighbors = net_params["use_neighbors"],
        use_masks = 1,
        predict_offsets = net_params["offsets"],
        offsets_input = net_params["offsets_input"],

        predict_smooth= training_param["predict_smooth"],
        smooth_suffix= prepare_param["smooth_suffix"],
        centers = json.load(open(data["scene_centers"])),
        padding = prepare_param["padding"],

        augmentation = 0,
        augmentation_angles = [],
        normalize =training_param["normalize"]


        )

    # train_loader = CustomDataLoader( batch_size = training_param["batch_size"],shuffle = True,drop_last = True,dataset = train_dataset,test=training_param["test"])
    # eval_loader = CustomDataLoader( batch_size = training_param["batch_size"],shuffle = False,drop_last = True,dataset = eval_dataset,test=training_param["test"])
    
    train_loader = CustomDataLoader( batch_size = batch_size,shuffle = True,drop_last = True,dataset = train_dataset,test=training_param["test"])
    eval_loader = CustomDataLoader( batch_size = batch_size,shuffle = False,drop_last = True,dataset = eval_dataset,test=training_param["test"])
    
    
    return train_loader,eval_loader,train_dataset,eval_dataset


# class MaskedLoss(nn.Module):
#     def __init__(self,criterion):
#         super(MaskedLoss, self).__init__()
#         self.criterion = criterion

#     def forward(self, outputs, targets, mask = None, first_only = 0):


#         if mask is not None:
#             loss =  self.criterion(outputs*mask, targets*mask)
            
#             # loss = loss.sum()/(mask.sum()/2.0)
#             loss = loss.sum()/(mask.sum())

#             return loss
#         else:
#             loss = self.criterion(outputs,targets)
#             loss = torch.mean(loss)
#             return loss 


class MaskedLoss(nn.Module):
    def __init__(self,criterion):
        super(MaskedLoss, self).__init__()
        self.criterion = criterion

    def forward(self, outputs, targets, mask = None, first_only = 1):

        if mask is None:
            mask = torch.ones_like(targets)
        
        if first_only:
            mask[:,1:,:,:] = 0
        
        loss =  self.criterion(outputs*mask, targets*mask)
        
        # loss = loss.sum()/(mask.sum()/2.0)
        loss = loss.sum()/(mask.sum())

        # mask.detach()

        return loss
        

def random_hyperparameters(hyperparameters):
    selected_params = {}
    for key in hyperparameters:
        selected_params[key] = random.sample(hyperparameters[key],1)[0]
    return selected_params

def split_train_eval_test(ids,train_scenes,test_scenes, eval_prop = 0.8):
    test_ids,train_ids,eval_ids = [],[],[]
    train = {}

    for id_ in ids:
        scene = id_.split("_")[0]
        if scene in test_scenes:
            test_ids.append(id_)
        elif scene in train_scenes:
            if scene not in train:
                train[scene] = []
            train[scene].append(id_)
    
    for key in train:
        nb_scene_samples = len(train[key])
        nb_train = int(eval_prop*nb_scene_samples)

        train_ids += train[key][:nb_train]
        eval_ids += train[key][nb_train:]

    return train_ids,eval_ids,test_ids


def min_max_scale(x,min_,max_,frange = (0,1)):
    x_std = (x - min_ )/(max_-min_)
    x_scaled = x_std * (frange[1]-frange[0]) + frange[0]
    return x_scaled

def revert_min_max_scale(x_scaled,min_,max_,frange = (0,1)):

    x_std = (x_scaled - frange[0]) / (frange[1]-frange[0]) 
    x = x_std * (max_-min_) + min_  
    return x

def standardization(x,mean_,std_):
    return (x - mean_) / std_

def revert_standardization(x_std,mean_,std_):
    return std_ * x_std + mean_
# def revert_scaling(ids,labels,outputs,inputs,scalers_root,multiple_scalers = 0):
# def revert_scaling(labels,outputs,inputs,scalers_root):

#     # if multiple_scalers:
#     #     scaler_ids = ["_".join(id_.split("_")[:-1]) for id_ in ids]
#     #     scalers_path = [scalers_root + id_ +".joblib" for id_ in scaler_ids]
       
#     #     scaler_sample = {}
#     #     for scaler in scalers_path:
#     #         if scaler not in scaler_sample:
#     #             scaler_sample[scaler] = []

#     #             for i,scaler1 in enumerate(scalers_path):
#     #                 if scaler == scaler1:
#     #                     scaler_sample[scaler].append(i)

#     #     for scaler_id in scaler_sample:
#     #         scaler = load(scaler_id)
#     #         samples_ids = scaler_sample[scaler_id]

#     #         sub_labels_torch = labels[samples_ids]
#     #         # b,a,s,i = sub_labels.size()

#     #         sub_labels = sub_labels_torch.contiguous().view(-1,1).cpu().numpy()
#     #         inv_sub_labels = torch.FloatTensor(scaler.inverse_transform(sub_labels)).view(sub_labels_torch.size()).cuda()
#     #         labels[samples_ids] = inv_sub_labels

#     #         sub_outputs_torch = outputs[samples_ids]
#     #         # b,a,s,i = sub_outputs.size()

#     #         sub_outputs = sub_outputs_torch.contiguous().view(-1,1).cpu().detach().numpy()
#     #         inv_sub_outputs = torch.FloatTensor(scaler.inverse_transform(sub_outputs)).view(sub_outputs_torch.size()).cuda()
#     #         outputs[samples_ids] = inv_sub_outputs
#     #     return labels,outputs
#     # else:

#     scaler = load(scalers_root)
#     torch_labels = labels.contiguous().cpu().numpy()
#     torch_outputs = outputs.contiguous().cpu().detach().numpy()
#     torch_inputs = inputs.contiguous().cpu().detach().numpy()

#     torch_labels = np.expand_dims(torch_labels.flatten(),1)
#     torch_outputs = np.expand_dims(torch_outputs.flatten(),1)
#     torch_inputs = np.expand_dims(torch_inputs.flatten(),1)



#     # non_zeros_labels = np.argwhere(torch_labels.reshape(-1))
#     # non_zeros_outputs = np.argwhere(torch_outputs.reshape(-1))

        
#     # torch_labels[non_zeros_labels] = np.expand_dims( scaler.inverse_transform(torch_labels[non_zeros_labels].squeeze(-1)) ,axis = 1)
    
#     # torch_outputs[non_zeros_outputs] = np.expand_dims( scaler.inverse_transform(torch_outputs[non_zeros_outputs].squeeze(-1)),axis = 1)
#     # torch_outputs[non_zeros_outputs] = np.expand_dims( scaler.inverse_transform(torch_outputs[non_zeros_outputs].squeeze(-1)),axis = 1)


        
#     torch_labels =  scaler.inverse_transform(torch_labels) 

#     torch_outputs = scaler.inverse_transform(torch_outputs)
#     torch_inputs =  scaler.inverse_transform(torch_inputs)

#     torch_labels = torch_labels.reshape(labels.size())
#     torch_outputs = torch_outputs.reshape(outputs.size())
#     torch_inputs = torch_inputs.reshape(inputs.size())




#     inv_labels = torch.FloatTensor(torch_labels).cuda()
#     inv_outputs = torch.FloatTensor(torch_outputs).cuda()
#     inv_inputs = torch.FloatTensor(torch_inputs).cuda()


#     inv_labels = inv_labels.view(labels.size())
#     inv_outputs = inv_outputs.view(outputs.size())
#     inv_inputs = inv_inputs.view(inputs.size())



#     return inv_labels,inv_outputs,inv_inputs


# def mask_loss(targets):
#     b,a = targets.shape[0],targets.shape[1]
#     mask = targets.reshape(b,a,-1)
#     mask = np.sum(mask,axis = 2)
#     mask = mask.reshape(-1)
#     mask = np.argwhere(mask).reshape(-1)
#     return mask  

def mask_loss(targets):
    n = targets.shape[0]
    mask = targets.reshape(n,-1)
    mask = np.sum(mask,axis = 1)
    mask = mask.reshape(-1)
    mask = np.argwhere(mask).reshape(-1)
    return mask  



def ade_loss(outputs,targets,mask = None,first_only = 1):

    if mask is None:
        mask = torch.ones_like(targets)

    if first_only:
        mask[:,1:,:,:] = 0

    # if mask is not None:
    outputs,targets = outputs*mask, targets*mask

    
    # outputs = outputs.contiguous().view(-1,2)
    # targets = targets.contiguous().view(-1,2)
    mse = nn.MSELoss(reduction= "none")
    

    mse_loss = mse(outputs,targets )
    mse_loss = torch.sum(mse_loss,dim = 3 )
    mse_loss = torch.sqrt(mse_loss )
    # if mask is not None:
    mse_loss = mse_loss.sum()/(mask.sum()/2.0)
    # else:
    #     mse_loss = torch.mean(mse_loss )

    return mse_loss

def fde_loss(outputs,targets,mask,first_only = 1):

    if mask is None:
        mask = torch.ones_like(targets)

    if first_only:
        mask[:,1:,:,:] = 0

    # if mask is not None:
    outputs,targets = outputs*mask, targets*mask

    b,n,s,i = outputs.size()

    outputs = outputs.view(b*n,s,i)
    targets = targets.view(b*n,s,i)
    mask = mask.view(b*n,s,i)




    ids = (mask.sum(dim = -1) > 0).sum(dim = -1)

    points_o = []
    points_t = []
    mask_n = []

    for seq_o,seq_t,m,id in zip(outputs,targets,mask,ids):
        if id == 0 or id == s:
            points_o.append(seq_o[-1])
            points_t.append(seq_t[-1])
            mask_n.append(m[-1])



        else:
            points_o.append(seq_o[id-1])
            points_t.append(seq_t[id-1])
            mask_n.append(m[id-1])

    points_o = torch.stack([po for po in points_o],dim = 0)
    points_t = torch.stack([pt for pt in points_t], dim = 0)
    mask_n = torch.stack([m for m in mask_n], dim = 0)




    mse = nn.MSELoss(reduction= "none")

    mse_loss = mse(points_o,points_t )
    mse_loss = torch.sum(mse_loss,dim = 1 )
    mse_loss = torch.sqrt(mse_loss )

    # if mask is not None:
    mask = mask[:,-1]
    mse_loss = mse_loss.sum()/(mask.sum()/2.0)
    # else:
    #     mse_loss = torch.mean(mse_loss )

    return mse_loss
# def ade_loss(outputs,targets,mask = None):



#     if mask is not None:
#         outputs,targets = outputs*mask, targets*mask

    
#     # outputs = outputs.contiguous().view(-1,2)
#     # targets = targets.contiguous().view(-1,2)
#     mse = nn.MSELoss(reduction= "none")
    

#     mse_loss = mse(outputs,targets )
#     mse_loss = torch.sum(mse_loss,dim = 3 )
#     mse_loss = torch.sqrt(mse_loss )
#     if mask is not None:
#         mse_loss = mse_loss.sum()/(mask.sum()/2.0)
#     else:
#         mse_loss = torch.mean(mse_loss )

#     return mse_loss

# def fde_loss(outputs,targets,mask):
#     if mask is not None:
#         outputs,targets = outputs*mask, targets*mask

#     b,n,s,i = outputs.size()

#     outputs = outputs.view(b*n,s,i)
#     targets = targets.view(b*n,s,i)
#     mask = mask.view(b*n,s,i)




#     ids = (mask.sum(dim = -1) > 0).sum(dim = -1)

#     points_o = []
#     points_t = []
#     mask_n = []

#     for seq_o,seq_t,m,id in zip(outputs,targets,mask,ids):
#         if id == 0 or id == s:
#             points_o.append(seq_o[-1])
#             points_t.append(seq_t[-1])
#             mask_n.append(m[-1])



#         else:
#             points_o.append(seq_o[id-1])
#             points_t.append(seq_t[id-1])
#             mask_n.append(m[id-1])

#     points_o = torch.stack([po for po in points_o],dim = 0)
#     points_t = torch.stack([pt for pt in points_t], dim = 0)
#     mask_n = torch.stack([m for m in mask_n], dim = 0)




#     mse = nn.MSELoss(reduction= "none")

#     mse_loss = mse(points_o,points_t )
#     mse_loss = torch.sum(mse_loss,dim = 1 )
#     mse_loss = torch.sqrt(mse_loss )

#     if mask is not None:
#         mask = mask[:,-1]
#         mse_loss = mse_loss.sum()/(mask.sum()/2.0)
#     else:
#         mse_loss = torch.mean(mse_loss )

#     return mse_loss


# def fde_loss(outputs,targets,mask):
#     if mask is not None:
#         outputs,targets = outputs*mask, targets*mask

    

#     outputs = outputs[:,:,-1,:]
#     targets = targets[:,:,-1,:]
#     mask = mask[:,:,-1,:]
#     mse = nn.MSELoss(reduction= "none")

#     mse_loss = mse(outputs,targets )
#     mse_loss = torch.sum(mse_loss,dim = 2 )
#     mse_loss = torch.sqrt(mse_loss )

#     if mask is not None:
#         mse_loss = mse_loss.sum()/(mask.sum()/2.0)
#     else:
#         mse_loss = torch.mean(mse_loss )

#     return mse_loss

# def get_colors(nb_colors,nb_colors_per_map = 20,maps = [cm.tab20,cm.tab20b,cm.tab20c,cm.gist_rainbow,cm.gist_ncar] ):
#     max_colors = len(maps) * nb_colors_per_map
#     if nb_colors >= max_colors:
#         return []
#     x = np.arange(nb_colors)
#     colors =  np.concatenate([ maps[int(i/nb_colors_per_map)]( np.linspace(0, 1, nb_colors_per_map)) for i in range( int(nb_colors/nb_colors_per_map) + 1 ) ], axis = 0)
#     return colors


def get_colors(nb_colors,nb_colors_per_map = 20,maps = [cm.tab20,cm.tab20b,cm.tab20c,cm.gist_rainbow,cm.gist_ncar] ):
    max_colors = len(maps) * nb_colors_per_map
    if nb_colors >= max_colors:
        return []

    nb_colors_per_map = int(nb_colors/len(maps)) + 1
    max_colors = len(maps) * nb_colors_per_map
    # print(nb_colors,nb_colors_per_map)
    # x = np.arange(nb_colors)

    colors =  np.concatenate([ map_( np.linspace(0, 1, nb_colors_per_map)) for map_ in maps ], axis = 0)

    ids = np.arange(max_colors)
    np.random.shuffle(ids)
    selected_ids = ids[:nb_colors]
    colors = colors[selected_ids]
    return colors


def plot_samples(kept_samples,epoch,n_columns = 2,n_rows = 2,root = "./data/reports/samples/"):
   
    n_plots = len(kept_samples)
    n_rows = 2
    n_columns = 1
    
    print("sample")
    for plot in range(n_plots):
        fig,axs = plt.subplots(n_rows,n_columns,sharex=True,sharey=True,squeeze = False)

        nb_colors = np.max([len(e) for e in kept_samples[plot]])
        colors = np.array(get_colors(nb_colors))

        if len(colors) > 0:          
            last_points = []
            r = 0
            c = 0
            for j,agent in enumerate(kept_samples[plot][0]):
                               

                color = colors[j]
                agent = agent.reshape(-1,2)

                
                agent = [e for e in agent if e[0]!=0 and e[1] != 0]
                

                if len(agent) > 0:

            
                    x = [e[0] for e in agent]
                    y = [e[1] for e in agent]
                    
                    axs[r][c].plot(x,y,color = color)

                    if j == 0:
                        axs[r][c].scatter(x,y,marker = "+",color = color,label = "obs")
                        axs[r][c].scatter(x[0],y[0],marker = ",",color = color,label = "obs_start")
                        axs[r][c].scatter(x[-1],y[-1],marker = "o",color = color,label = "obs_end")
                    else :

                        axs[r][c].scatter(x,y,marker = "+",color = color)
                        axs[r][c].scatter(x[0],y[0],marker = ",",color = color)
                        axs[r][c].scatter(x[-1],y[-1],marker = "o",color = color)
                else:
                    print("input agents zeros")

                        
                last_points.append([x[-1],y[-1]])

            for j,agent in enumerate(kept_samples[plot][1]):
                color = colors[j]                    
                
                agent = agent.reshape(-1,2)
                agent = [e for e in agent if e[0]!=0 and e[1] != 0]

                if len(agent) > 0:
                    x = [last_points[j][0]] + [e[0] for e in agent]
                    y = [last_points[j][1]]+[e[1] for e in agent]
                    
                    
                    axs[r][c].plot(x,y,color = color)
                    axs[r][c].scatter(x,y,marker = "+",color = color)
                    
                    if j == 0:
                        axs[r][c].scatter(x[-1],y[-1],marker = "v",color = color,label = "gt_end")
                    else:
                        
                        axs[r][c].scatter(x[-1],y[-1],marker = "v",color = color)
                else:
                    print("labels agents zeros")



            axs[r][c].legend(loc='upper center', bbox_to_anchor=(1.45, 1))

            r = 1
            c = 0


            for j,agent in enumerate(kept_samples[plot][0]):
                color = colors[j]
                agent = agent.reshape(-1,2)
                agent = [e for e in agent if e[0]!=0 and e[1] != 0]

                if len(agent) > 0:

                    x = [e[0] for e in agent]
                    y = [e[1] for e in agent]
                    axs[r][c].plot(x,y,color = color)

                    if j == 0:
                        axs[r][c].scatter(x,y,marker = "+",color = color,label = "obs")
                        axs[r][c].scatter(x[0],y[0],marker = ",",color = color,label = "obs_start")
                        axs[r][c].scatter(x[-1],y[-1],marker = "o",color = color,label = "obs_end")
                    else :
                        axs[r][c].scatter(x,y,marker = "+",color = color)
                        axs[r][c].scatter(x[0],y[0],marker = ",",color = color)
                        axs[r][c].scatter(x[-1],y[-1],marker = "o",color = color)
                else:
                    print("input agents zeros 2")

            for j,agent in enumerate(kept_samples[plot][2]):
                color = colors[j]
                agent = agent.reshape(-1,2)
                agent = [e for e in agent if e[0]!=0 and e[1] != 0]

                if len(agent) > 0:
                
                    x = [e[0] for e in agent]
                    y = [e[1] for e in agent]
                    if j == 0:
                        axs[r][c].scatter(x,y,label = "pred",marker = "x",color = color)
                        axs[r][c].scatter(x[0],y[0],marker = "o",color = color,label = "pred_start")
                        axs[r][c].scatter(x[-1],y[-1],marker = "v",color = color,label = "pred_end")
                    else:
                        axs[r][c].scatter(x,y,marker = "x",color = color)
                        axs[r][c].scatter(x[0],y[0],marker = "o",color = color)
                        axs[r][c].scatter(x[-1],y[-1],marker = "v",color = color)
                else:
                    print("pred agents zeros ")
        
            # axs[r][c].legend()
            plt.savefig("{}samples_{}_epoch_{}.jpg".format(root,plot,epoch))
            plt.close()

            tensor = {
                "inputs": kept_samples[plot][0].tolist(),
                "predictions": kept_samples[plot][2].tolist(),
                "outputs": kept_samples[plot][1].tolist()

            }

            json.dump(tensor,open("{}samples_{}_epoch_{}.json".format(root,plot,epoch),"w"))



def plot_grad_flow(named_parameters,epoch,root = "./data/reports/gradients/"):
    '''Plots the gradients flowing through different layers in the net during training.
    Can be used for checking for possible gradient vanishing / exploding problems.
    
    Usage: Plug this function in Trainer class after loss.backwards() as 
    "plot_grad_flow(self.model.named_parameters())" to visualize the gradient flow'''
    ave_grads = []
    max_grads= []
    layers = []
    for n, p in named_parameters:
        if(p.requires_grad) and ("bias" not in n):
            
            layers.append(n)
            ave_grads.append(p.grad.abs().mean())
            max_grads.append(p.grad.abs().max())
    
    fig, ax = plt.subplots()

    print("*** {} ****".format(ave_grads))
    print("")
    ax.bar(np.arange(len(max_grads)), max_grads, alpha=0.1, lw=1, color="c")
    ax.bar(np.arange(len(max_grads)), ave_grads, alpha=0.1, lw=1, color="b")
    ax.hlines(0, 0, len(ave_grads)+1, lw=2, color="k" )
    ax.set_xticks(range(0, len(ave_grads), 1))
    ax.set_xticklabels(layers, rotation='vertical', fontsize='small')
    ax.set_yscale('log')
    ax.set_xlabel("Layers")
    ax.set_ylabel("Gradient magnitude")
    ax.set_title('Gradient flow')
    ax.grid(True)
    lgd = ax.legend([Line2D([0], [0], color="c", lw=4),
                Line2D([0], [0], color="b", lw=4),
                Line2D([0], [0], color="k", lw=4)], ['max-gradient', 'mean-gradient', 'zero-gradient'])

    # plt.savefig("{}gradients_{}.jpg".format(root,epoch), bbox_extra_artists=(lgd,), bbox_inches='tight')
    plt.savefig("{}gradients_{}.jpg".format(root,time.time()), bbox_extra_artists=(lgd,), bbox_inches='tight')

    plt.close()

def plot_params(named_parameters,epoch,root="./data/reports/weights/"):
    weights = {}
    for n,p in named_parameters:
        if(p.requires_grad) :
            weights[n] = p.cpu().detach().numpy().flatten()

    n_rows = int(np.ceil( np.sqrt(len(weights))) )


    fig,axs = plt.subplots(n_rows-1,n_rows,sharex=False,sharey=False,squeeze = False)
    ctr = 0
    fig.set_figheight(15)
    fig.set_figwidth(30)

    layers = list(weights.keys())
    
    for i in range(n_rows-1 ):
        for j in range(n_rows):

            if ctr < len(weights) :
                axs[i][j].hist(weights[layers[ctr]],label = layers[ctr],bins = 20)
                # axs[i][j].set_title("weights {}".format(layers[ctr]))
                lgd = axs[i][j].legend()
            ctr += 1
    fig.tight_layout()
    plt.savefig("{}epoch_{}__{}.jpg".format(root,epoch,time.time()))
    plt.close()

def augment_scene_list(scene_list,angles):
    new_list = []

    for scene in scene_list:
        new_list.append(scene)
        for angle in angles:
            scene_angle = scene + "_{}".format(angle)
            new_list.append(scene_angle)
    return new_list
    

def offsets_to_trajectories(inputs,labels,outputs,offsets,offsets_input,last_points,input_last):
    # print(inputs.shape) # B,N,obs,2
    # print(labels.shape) # B,N,pred,2
    # print(outputs.shape) # B,N,pred,2

    if offsets_input == 1:
        inputs = input_last
    
    if offsets == 1:
        # last_points = np.repeat(  np.expand_dims(inputs[:,:,-1],2),  labels.shape[2], axis=2)
        labels = np.add(last_points,labels)
        outputs = np.add(last_points,outputs)
        return inputs,labels,outputs
    elif offsets == 2:
        print("offset 2 not allowed")
        # # seq = np.concatenate([inputs,labels],axis = 2)
        # # last_points = seq[:,:,inputs.shape[2]-1:seq.shape[2]-1]
        # last_points = np.repeat(  np.expand_dims(inputs[:,:,-1],2),  labels.shape[2], axis=2)# B,N,pred,2

        # labels = np.concatenate([np.expand_dims( np.add(last_points[:,:,i], np.sum(labels[:,:,:i+1],axis = 2)), 2) for i in range(labels.shape[2])], axis = 2)
        # outputs = np.concatenate([np.expand_dims( np.add(last_points[:,:,i], np.sum(outputs[:,:,:i+1],axis = 2)), 2) for i in range(outputs.shape[2])], axis = 2)


        # return inputs,labels,outputs
    else :
        return inputs,labels,outputs



import torch.nn.init as init


def weight_init(m):
    '''
    Usage:
        model = Model()
        model.apply(weight_init)
    '''
    
    if isinstance(m, nn.Linear):
        init.xavier_normal_(m.weight.data,gain=nn.init.calculate_gain('relu'))
        init.normal_(m.bias.data)
    elif isinstance(m, nn.Conv1d):
        init.xavier_normal_(m.weight.data,gain=nn.init.calculate_gain('relu'))
        # init.xavier_normal_(m.weight_g.data,gain=nn.init.calculate_gain('relu'))
        # init.xavier_normal_(m.weight_v.data,gain=nn.init.calculate_gain('relu'))

        init.normal_(m.bias.data)
        # init.normal_(m.weight.data)
        # if m.bias is not None:
        #     init.normal_(m.bias.data)
    
    
    