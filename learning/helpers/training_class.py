import torch
import time
import matplotlib.pyplot as plt
import torch
import torch.nn as nn
import numpy as np
from joblib import load
import helpers.helpers_training as helpers
import os
from scipy import stats
# from tensorboardX import SummaryWriter


class NetTraining():
    def __init__(self,args):
        self.args = args 
        self.n_epochs = args["n_epochs"]
        self.batch_size = args["batch_size"]
        self.device = args["device"]
        self.train_loader = args["train_loader"]
        self.eval_loader = args["eval_loader"]
        self.criterion = args["criterion"]
        self.optimizer = args["optimizer"]
        self.use_neighbors = args["use_neighbors"]
        self.scalers_path = args["scalers_path"]
        self.plot = args["plot"]
        self.load_path = args["load_path"]
        self.plot_every = args["plot_every"]
        self.save_every = args["save_every"]
        self.offsets = args["offsets"]
        self.normalized = args["normalized"]
        self.net = args["net"]
        self.print_every = args["print_every"]
        self.nb_grad_plots = args["nb_grad_plots"]
        self.nb_sample_plots = args["nb_sample_plots"]
        self.train_model = args["train"]


    def training_loop(self):
        losses = {
        "train":{ "loss": []},
        "eval":{
            "loss": [],
            "fde":[],
            "ade":[]}
        }

        start_epoch = 0
        s = time.time()

        if self.load_path != "":
            print("loading former model from {}".format(self.load_path))
            checkpoint = torch.load(self.load_path)
            self.net.load_state_dict(checkpoint['state_dict'])
            self.optimizer.load_state_dict(checkpoint['optimizer'])
            losses = checkpoint["losses"]
            start_epoch = checkpoint["epoch"]

        try:
            best_harmonic_fde_ade = float('inf')
            for epoch in range(start_epoch,self.n_epochs):
                train_loss = 0.
                if self.train_model:
                    train_loss,_ = self.train(epoch)
                eval_loss,fde,ade = self.evaluate(epoch)
                    
                

                losses["train"]["loss"].append(train_loss)
                losses["eval"]["loss"].append(eval_loss)
                losses["eval"]["ade"].append(ade)
                losses["eval"]["fde"].append(fde)


                if self.plot and epoch % self.plot_every == 0:
                    self.plot_losses(losses,s,root = "./data/reports/losses/")

                if epoch % self.save_every == 0:
                    self.save_model(epoch,epoch,self.net,self.optimizer,losses)

                h = stats.hmean([ade,fde])

                if h < best_harmonic_fde_ade:
                    print("harmonic mean {} is better than {}, saving new best model!".format(h,best_harmonic_fde_ade))
                    self.save_model(epoch,"best",self.net,self.optimizer,losses,remove=0)
                    best_harmonic_fde_ade = h

                print(time.time()-s)
            
        
        except Exception as e: 
            print(e)

    s = time.time()
    



    """
        Train loop for an epoch
        Uses cuda if available
        LOss is averaged for a batch
        THen averaged batch losses are averaged
        over the number of batches
    """
    def train(self,epoch):
        self.net.train()
        epoch_loss = 0.
        batches_loss = []
        
        self.nb_grad_plots = 1
        ids_grads = np.arange(int(self.train_loader.nb_batches) )
        np.random.shuffle(ids_grads)
        ids_grads = ids_grads[:self.nb_grad_plots]

        torch.cuda.synchronize()
        start_time = time.time()
        
        for batch_idx, data in enumerate(self.train_loader):
            
            # Load data
            inputs, labels,types,points_mask, active_mask, imgs = data
            inputs = inputs.to(self.device)
            labels =  labels.to(self.device)
            types =  types.to(self.device)
            imgs =  imgs.to(self.device)        
            active_mask = active_mask.to(self.device)
            
            # gradients to zero
            self.optimizer.zero_grad()
            # predict using network
            outputs = self.net((inputs,types,active_mask,points_mask,imgs))
    
            # keep mask for prediction part only
            points_mask = points_mask[1]
            points_mask = torch.FloatTensor(points_mask).to(self.device)

            # mask output and label si that padding not used for prediction, no gradients
            outputs = torch.mul(points_mask,outputs)
            labels = torch.mul(points_mask,labels)

            # compute loss and backprop
            loss = self.criterion(outputs, labels,points_mask)
            loss.backward()

            if batch_idx in ids_grads:
                # plot layers weights distributions
                try:
                    helpers.plot_params(self.net.named_parameters(),epoch)
                except Exception as e: 
                    print(e)
                # plot layers gradients
                try:
                    helpers.plot_grad_flow(self.net.named_parameters(),epoch)
                except Exception as e: 
                    print(e)

            self.optimizer.step()

            epoch_loss += loss.item()
            batches_loss.append(loss.item())

            # print batch loss <-- mean batch loss for last print_every timesteps
            if batch_idx % self.print_every == 0:
                print(batch_idx,loss.item(),time.time()-start_time)     
        epoch_loss = np.median(batches_loss) 
        epoch_loss = np.mean(batches_loss)  

        print('Epoch n {} Loss: {}'.format(epoch,epoch_loss))

        return epoch_loss,batches_loss



    """
        Evaluation loop for an epoch
        Uses cuda if available
        LOss is averaged for a batch
        THen averaged batch losses are averaged
        over the number of batches

        FDE loss is added using MSEerror on the last point of prediction and target
        sequences

        model: 0 rnn_mlp
            1 iatcnn
    """
    def evaluate(self,epoch):
        self.net.eval()
        eval_loss = 0.
        fde = 0.
        ade = 0.
        eval_loader_len =   float(self.eval_loader.nb_batches)

        batch_losses = []

        nb_batches = self.eval_loader.nb_batches
        kept_batches_id = np.arange(nb_batches)
        np.random.shuffle(kept_batches_id)

        kept_batches_id = kept_batches_id[:self.nb_sample_plots]

        kept_samples = []
        for i,data in enumerate(self.eval_loader):
            keep_batch = (i in kept_batches_id )

            # Load data
            inputs, labels,types,points_mask, active_mask, imgs = data
            inputs = inputs.to(self.device)
            labels =  labels.to(self.device)
            types =  types.to(self.device)
            imgs =  imgs.to(self.device)        
            active_mask = active_mask.to(self.device)
            
            outputs = self.net((inputs,types,active_mask,points_mask,imgs))
            
            if self.normalized:
                _,_,inputs = helpers.revert_scaling(labels,outputs,inputs,self.scalers_path)            
                outputs = outputs.view(labels.size())
                inputs,labels,outputs = helpers.offsets_to_trajectories(inputs.detach().cpu().numpy(),
                                                                    labels.detach().cpu().numpy(),
                                                                    outputs.detach().cpu().numpy(),
                                                                    self.offsets)
           
            inputs,labels,outputs = torch.FloatTensor(inputs).to(self.device),torch.FloatTensor(labels).to(self.device),torch.FloatTensor(outputs).to(self.device)
            

            # we don't count the prediction error for end of trajectory padding
            points_mask = points_mask[1]

            points_mask = torch.FloatTensor(points_mask).to(self.device)#
            outputs = torch.mul(points_mask,outputs)#
            labels = torch.mul(points_mask,labels)#


            loss = self.criterion(outputs, labels,points_mask)
            batch_losses.append(loss.item())

            if keep_batch:
                kept_sample_id = np.random.randint(0,labels.size()[0])

                l = labels[kept_sample_id]
                o = outputs[kept_sample_id,:,:,:2]
                ins = inputs[kept_sample_id]

                # if model doesn't take neighboors into account, add a dimension
                if self.use_neighbors == 0: 
                    ins = inputs[kept_sample_id].unsqueeze(0)
                elif self.use_neighbors == 1:

                    sample_mask = points_mask[kept_sample_id]
                    
                    # keep only active agents
                    kept_mask = helpers.mask_loss(sample_mask.detach().cpu().numpy())   
                    l = l[kept_mask]
                    o = o[kept_mask]
                    ins = ins[kept_mask]


                kept_samples.append((
                    ins.detach().cpu().numpy(),
                    l.detach().cpu().numpy(),
                    o.detach().cpu().numpy()
                    ))

            ade += helpers.ade_loss(outputs,labels,points_mask).item() ######
            fde += helpers.fde_loss(outputs,labels,points_mask).item()
        
            eval_loss += loss.item()
        
        try:
            helpers.plot_samples(kept_samples,epoch,1,1) #### retrieve 
        except Exception as e: 
            print(e)

        eval_loss = np.median(batch_losses)
        eval_loss = np.mean(batch_losses)


        ade /= eval_loader_len      
        fde /= eval_loader_len        

        print('Epoch n {} Evaluation Loss: {}, ADE: {}, FDE: {}'.format(epoch,eval_loss,ade,fde))


        return eval_loss,fde,ade


    def analysis_curves(self,nb_samples,batch_props,args):
        print("nb samples train {}".format(nb_samples))


        train_errors = []
        dev_errors = [] 
        nb_samples_kept = []
        desired_perfs = []

        print("learning curves")
        for prop in batch_props:

            self.__init__(args)

            print("**** proportion of train samples *** {}".format(prop))
            self.train_loader.data_len = int( prop * nb_samples)
            print("nb of kept train samples {}".format(self.train_loader.data_len))
            self.train_loader.split_batches()
            print("nb of kept batches {}".format(self.train_loader.nb_batches))

            


            for epoch in range(self.n_epochs):
                self.train(epoch)

            train_loss,_,_ = self.evaluate_analysis(self.train_loader)
            eval_loss,_,_ = self.evaluate_analysis(self.eval_loader)
        
            train_errors.append(train_loss)
            dev_errors.append(eval_loss)
            nb_samples_kept.append(int( prop * nb_samples))
            desired_perfs.append(0.)

        plt.plot(nb_samples_kept,train_errors,label = "train_error")
        plt.plot(nb_samples_kept,dev_errors,label = "dev_error")
        plt.plot(nb_samples_kept,desired_perfs,label = "desired_perfs")

        plt.ylabel("loss function")
        plt.xlabel("nb train samples")

        plt.legend()

        plt.savefig("{}learning_curves.jpg".format("./data/reports/analysis_curves/"))
        plt.close()


    def evaluate_analysis(self,eval_loader):
        self.net.eval()
        eval_loss = 0.
        fde = 0.
        ade = 0.
        eval_loader_len =   float(eval_loader.nb_batches)

        batch_losses = []

        
        for i,data in enumerate(eval_loader):

            # Load data
            inputs, labels,types,points_mask, active_mask, imgs = data
            inputs = inputs.to(self.device)
            labels =  labels.to(self.device)
            types =  types.to(self.device)
            imgs =  imgs.to(self.device)        
            active_mask = active_mask.to(self.device)
            
            outputs = self.net((inputs,types,active_mask,points_mask,imgs))
            
            if self.normalized:
                _,_,inputs = helpers.revert_scaling(labels,outputs,inputs,self.scalers_path)            
                outputs = outputs.view(labels.size())
                inputs,labels,outputs = helpers.offsets_to_trajectories(inputs.detach().cpu().numpy(),
                                                                    labels.detach().cpu().numpy(),
                                                                    outputs.detach().cpu().numpy(),
                                                                    self.offsets)
           
            inputs,labels,outputs = torch.FloatTensor(inputs).to(self.device),torch.FloatTensor(labels).to(self.device),torch.FloatTensor(outputs).to(self.device)
            

            # we don't count the prediction error for end of trajectory padding
            points_mask = points_mask[1]

            points_mask = torch.FloatTensor(points_mask).to(self.device)#
            outputs = torch.mul(points_mask,outputs)#
            labels = torch.mul(points_mask,labels)#


            loss = self.criterion(outputs, labels,points_mask)
            batch_losses.append(loss.item())

            

            ade += helpers.ade_loss(outputs,labels,points_mask).item() ######
            fde += helpers.fde_loss(outputs,labels,points_mask).item()
        
            eval_loss += loss.item()
       

        eval_loss = np.median(batch_losses)
        eval_loss = np.mean(batch_losses)


        ade /= eval_loader_len      
        fde /= eval_loader_len        

        print('Evaluation Loss: {}, ADE: {}, FDE: {}'.format(eval_loss,ade,fde))
        return eval_loss,fde,ade

    def plot_losses(self,losses,idx,root = "./data/reports/losses/"):
        plt.plot(losses["train"]["loss"],label = "train_loss")
        plt.plot(losses["eval"]["loss"],label = "eval_loss")
        plt.legend()

        # plt.show()
        plt.savefig("{}losses_{}.jpg".format(root,idx))
        plt.close()

        plt.plot(losses["eval"]["ade"],label = "ade")
        plt.plot(losses["eval"]["fde"],label = "fde")
        plt.legend()

        plt.savefig("{}ade_fde_{}.jpg".format(root,idx))
        plt.close()




    """
        Saves model and optimizer states as dict
        THe current epoch is stored
        THe different losses at previous time_steps are loaded

    """
    def save_model(self,epoch,name,net,optimizer,losses,remove = 1,save_root = "./learning/data/models/" ):

        dirs = os.listdir(save_root)

        # save_path = save_root + "model_{}_{}.tar".format(name,time.time())
        save_path = save_root + "model_{}.tar".format(name)


        print("args {}".format(net.args))
        state = {
            'epoch': epoch,
            'state_dict': net.state_dict(),
            # 'named_parameters': net.named_parameters(),

            'optimizer': optimizer.state_dict(),             
            'losses': losses,
            'args': net.args
            }
        # state = {
        #     'state_dict': net.state_dict(),
        #     }
        torch.save(state, save_path)

        if remove:
            for dir_ in dirs:
                if dir_ != "model_best.tar":
                    os.remove(save_root+dir_)
        
        print("model saved in {}".format(save_path))






