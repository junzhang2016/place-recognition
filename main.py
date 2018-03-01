import io
from PIL import Image
import numpy as np
import time
import math
import matplotlib.pyplot as plt

import argparse
import torch
import torch.optim as optim
from torchvision import transforms
from torch.autograd import Variable

import model
from dataset import TripletImageLoader
from tripletnet import TripletNet

model = model.Net()

def train_model(train_loader, tripletnet, criterion, optimizer, epoch):
    # switch to train mode
    tripletnet.train()
    for batch_idx, (anchor, positive, negative) in enumerate(train_loader):
        if torch.cuda.is_available():
            anchor, positive, negative = anchor.cuda(), positive.cuda(), negative.cuda()
        anchor, positive, negative = Variable(anchor), Variable(positive), Variable(negative)

#        f, axarr = plt.subplots(2,2)
#        axarr[0,0].imshow(anchor[0].data.cpu().numpy().transpose((1, 2, 0)))
#        axarr[0,1].imshow(positive[0].data.cpu().numpy().transpose((1, 2, 0)))
#        axarr[1,0].imshow(negative[0].data.cpu().numpy().transpose((1, 2, 0)))
#        plt.show()

        # compute output
        dist_a, dist_b, embedded_x, embedded_y, embedded_z = tripletnet(anchor, positive, negative)
        # 1 means, dist_a should be larger than dist_b
        target = torch.FloatTensor(dist_a.size()).fill_(1)
        if torch.cuda.is_available():
            target = target.cuda()
        target = Variable(target)
        
        loss_triplet = criterion(dist_a, dist_b, target)
        loss_embedd = embedded_x.norm(2) + embedded_y.norm(2) + embedded_z.norm(2)
        loss = loss_triplet + 0.001 * loss_embedd

        # compute gradient and do optimizer step
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        print (loss)

def train(datapath, epochs, args):
    global model

    model.train()

    normalize = transforms.Normalize(
        #mean=[121.50361069 / 127., 122.37611083 / 127., 121.25987563 / 127.],
        mean=[1., 1., 1.],
        std=[1 / 127., 1 / 127., 1 / 127.]
    )

    preprocess = transforms.Compose([
        transforms.Resize(227),
        transforms.CenterCrop(227),
        transforms.ToTensor(),
#        normalize
    ])

    kwargs = {'num_workers': 1, 'pin_memory': True} if torch.cuda.is_available() else {}
    train_loader = torch.utils.data.DataLoader(TripletImageLoader(datapath, size=100000, transform=preprocess), batch_size=args.bsize, shuffle=True, **kwargs)

    tripletnet = TripletNet(model)

    criterion = torch.nn.MarginRankingLoss(margin=args.margin)
    optimizer = optim.SGD(tripletnet.parameters(), lr=args.lr, momentum=args.momentum)
    for epoch in range(1, epochs + 1):
        # train for one epoch
        train_model(train_loader, tripletnet, criterion, optimizer, epoch)
#        # evaluate on validation set
#        acc = test(test_loader, tripletnet, criterion, epoch)
#
#        # remember best acc and save checkpoint
#        is_best = acc > best_acc
#        best_acc = max(acc, best_acc)
        state = {
            'epoch': epoch + 1,
            'tripletnet_state_dict': tripletnet.state_dict(),
            'state_dict': model.state_dict(),
        }
        torch.save(state, "checkpoints/new.pth")

def test(datapath):
    model.eval()
    model.training = False

    normalize = transforms.Normalize(
        #mean=[121.50361069 / 127., 122.37611083 / 127., 121.25987563 / 127.],
        mean=[1., 1., 1.],
        std=[1 / 127., 1 / 127., 1 / 127.]
    )

    preprocess = transforms.Compose([
        transforms.Resize(227),
        transforms.CenterCrop(227),
        transforms.ToTensor(),
        normalize
    ])

    with open(datapath, 'r') as reader:
        reps = []
        for image_path in reader:
            image_path = image_path.strip()
            image = Image.open(image_path).convert('RGB')
            image_tensor = preprocess(image)
            image_tensor.unsqueeze_(0)
            image_variable = Variable(image_tensor).cuda()
            features = model.features_extraction(image_variable)
            reps.append(features)

        for i in range(len(reps)):
            print ("\n\n")
            for j in range(len(reps)):
                d = np.asarray(reps[j].data - reps[i].data)
                # similarity = np.dot(d, d)
                similarity = np.linalg.norm(d)
                print (i, j, similarity)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='PyTorch on TORCS with Multi-modal')

    parser.add_argument('--mode', default='test', type=str, help='support option: train/test')
    parser.add_argument('--datapath', default='datapath', type=str, help='path st_lucia dataset')
    parser.add_argument('--bsize', default=10, type=int, help='minibatch size')
    parser.add_argument('--margin', type=float, default=0.2, metavar='M', help='margin for triplet loss (default: 0.2)')
    parser.add_argument('--lr', type=float, default=0.01, metavar='LR', help='learning rate (default: 0.01)')
    parser.add_argument('--momentum', type=float, default=0.5, metavar='M', help='SGD momentum (default: 0.5)')
    parser.add_argument('--tau', default=0.001, type=float, help='moving average for target network')
    parser.add_argument('--debug', dest='debug', action='store_true')
    parser.add_argument('--train_iter', default=20000000, type=int, help='train iters each timestep')
    parser.add_argument('--epsilon', default=50000, type=int, help='linear decay of exploration policy')
    parser.add_argument('--checkpoint', default="checkpoints", type=str, help='Checkpoint path')
    args = parser.parse_args()

    global model
    checkpoint = torch.load(args.checkpoint)
    model.load_state_dict(checkpoint['state_dict'])
    if torch.cuda.is_available():
        model.cuda()

    args = parser.parse_args()
    if args.mode == 'train':
        train(args.datapath, args.train_iter, args)
    elif args.mode == 'test':
        test(args.datapath)
    else:
        raise RuntimeError('undefined mode {}'.format(args.mode))

