#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import os
from math import log, floor, sqrt

import mxnet as mx
import numpy as np
import cv2
from mxnet.gluon.data import Dataset, DataLoader


# In[ ]:


class ReadDataSet(Dataset):
    def __init__(self, root, split, transform=None, use_mask=False, fixed_weight=False, log_weight=False, log_base=2):
        self.root = os.path.join(root, split)
        self.transform = transform
        self.fixed_weight = fixed_weight
        self.fix_weight = [0.3659,0.5685,0.0398,0.0139,0.0119]
        self.img_paths = []
        self.log_weight = log_weight
        if log_weight:
            tmp = [0.3659,0.5685,0.0398,0.0139,0.0119]
            self.fix_weight = [-log(tmp[0],log_base), 
                               -log(tmp[1],log_base),
                               -log(tmp[2],log_base),
                               -log(tmp[3],log_base),
                               -log(tmp[4],log_base)]
            
        self._img = os.path.join(root, split, 'images', '{}.jpg')
        self._use_mask = use_mask
        if self._use_mask:
            self._mask = os.path.join(root, split, 'mask', '{}.png')
        self._lbl = os.path.join(root, split, 'labels', '{}.png')
        
        for fn in os.listdir(os.path.join(root, split, 'labels')):
            if len(fn) > 3 and fn[-4:] == '.png':
                self.img_paths.append(fn[:-4])
        
    def __len__(self):
        return len(self.img_paths)
    
    def __getitem__(self, idx):
#         print(self.img_paths[idx])
        img_path = self._img.format(self.img_paths[idx])
#         print(img_path)
        if self._use_mask:
            mask_path = self._mask.format(self.img_paths[idx])
        lbl_path = self._lbl.format(self.img_paths[idx])

        img = cv2.imread(img_path)

        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        lbl = cv2.imread(lbl_path, cv2.IMREAD_GRAYSCALE)

#         print('label read',np.min(lbl),np.max(lbl))
        unique, counts = np.unique(lbl, return_counts=True)
        lbl_map = unique
        
        if not self.fixed_weight:
            all_count = np.prod(lbl.shape)

            
            instance_weight = {}
            for cls, counts in zip(unique, counts):
                instance_weight[cls] = -log(counts / all_count)
    #             instance_weight[cls] = (all_count - counts) / all_count

    #         instance_weight = 1 - instance_weight
            print(instance_weight)
#         fg_count = np.count_nonzero(lbl)
#         bg_count = all_count - fg_count
#         alpha = 1. / fg_count
#         beta = 1. / bg_count

#         alpha = alpha / (alpha + beta)
#         beta = beta / (alpha + beta)

        if self._use_mask:
            mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)
            mask = np.bitwise_not(mask)
            lbl = np.bitwise_or(mask, lbl/255)
#         else:
#             lbl = lbl / 255
        
#         print('label read after /255',np.min(lbl),np.max(lbl))    

        if self.transform is not None:
            img, lbl = self.transform(img, lbl)

        weight_map = mx.nd.zeros(lbl.shape)
        lb_np = lbl.asnumpy()
        
        if not self.fixed_weight:
            unique, counts = np.unique(lb_np, return_counts=True)
            print(unique, counts)
            for cls in unique:
    #             print(cls)
                if cls in instance_weight.keys():
                    d,x,y = np.where(lb_np == cls)
                    weight_map[(d,x,y)] = instance_weight[cls]

    #         print(weight_map)
    #         weight = lbl * alpha + (1 - lbl) * beta

        else:
            wtmap = self.fix_weight
            if not self.log_weight:
                wtmap = 1- np.array(self.fix_weight)
 
            for cls in range(len(self.fix_weight)):
                d,x,y = np.where(lb_np == cls)
                if (len(d) > 0):
                    weight_map[(d,x,y)] = wtmap[cls]
                
#         print("lbl_map",lbl_map)
        return img, lbl, weight_map, lbl_map


# In[ ]:


class ReadDataSet_micro(Dataset):
    def __init__(self, root, split, nb_cls, ctx, transform=None, read_label=True):
        self.root = os.path.join(root, split)
        self.transform = transform
        self.nb_cls = nb_cls
        self.ctx = ctx
        self.read_label = read_label
        self.img_paths = []
        
        self._img = os.path.join(root, split, 'images', '{}.jpg')
        self._lbl = os.path.join(root, split, 'labels', '{}.txt')
        
        for fn in os.listdir(os.path.join(root, split, 'images')):
            if len(fn) > 3 and fn[-4:] == '.jpg':
                self.img_paths.append(fn[:-4])
        
    def __len__(self):
        return len(self.img_paths)
    
    def __getitem__(self, idx):
#         print(self.img_paths[idx])
        img_path = self._img.format(self.img_paths[idx])
#         print(img_path)

        img = cv2.imread(img_path)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        if self.read_label:
            lbl_path = self._lbl.format(self.img_paths[idx])
            f = open(lbl_path, "r")
            lbl = [int(f.readline())]
            f.close()
            lbl = mx.nd.array(lbl, ctx=self.ctx)
        else:
            lbl = mx.nd.array([-1], ctx=self.ctx)
        if self.transform is not None:
            img, _ = self.transform(img)
        with open('stat_file_names.txt', 'a+') as file:
            file.write(self.img_paths[idx]+'.jpg\n')

        return img, lbl


# In[ ]:


class ReadDataSet_multi(Dataset):
    def __init__(self, root, split, nb_cls, ctx, transform=None, use_mask=False):
        self.root = os.path.join(root, split)
        self.transform = transform
        self.nb_cls = nb_cls
        self.ctx = ctx
        self.img_paths = []
        
        if (split == 'test'):
            self._img = os.path.join(root, split, 'images', '{}.jpg')

            for fn in os.listdir(os.path.join(root, split, 'images')):
                if len(fn) > 3 and fn[-4:] == '.jpg':
                    self.img_paths.append(fn[:-4])
                    
        else:
            self._img = os.path.join(root, split, 'images', '{}.png')

            for fn in os.listdir(os.path.join(root, split, 'images')):
                if len(fn) > 3 and fn[-4:] == '.png':
                    self.img_paths.append(fn[:-4])
        
    def __len__(self):
        return len(self.img_paths)
    
    def __getitem__(self, idx):
#         print(self.img_paths[idx])
        img_path = self._img.format(self.img_paths[idx])
#         print(img_path)

        img = cv2.imread(img_path)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        fname = self.img_paths[idx]
        _, features = fname.split("-")
        features = [int(x) for x in features.split(",")]
        features = np.array(features) - 1
        lbl = np.zeros((self.nb_cls,1))
        for f in features:
            lbl[f,0] = 1
        
        lbl = mx.nd.array(lbl, ctx=self.ctx)

        if self.transform is not None:
            img, _ = self.transform(img)

        return img, lbl

