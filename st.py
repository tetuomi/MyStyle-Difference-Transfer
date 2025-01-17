import os
import sys
import os.path
import argparse
from glob import glob

import torch
import torch.nn as nn
from torch import optim
from torch.autograd import Variable

import matplotlib.pyplot as plt

from utility.utility import *
from utility.vgg_network import VGG
from utility.disentangle_model import DISENTANGLE_MODEL
from utility.models_wo_relu import DISENTANGLE_MODEL as DISENTANGLE_MODEL2
from utility.vgg_network_with_top import VGG as VGGWithTOP
#############################################################################
# PARSER
parser = argparse.ArgumentParser(description='Style Difference Transfer')
# parameters
parser.add_argument('--alpha', '-alpha', type=float, default = 1, help='parameter for content loss')
parser.add_argument('--beta', '-beta', type=float, default = 1, help='parameter for style loss')
# Parser for style weights
parser.add_argument('--sw1', '-sw1', type=float,  default=1, help='sw1')
parser.add_argument('--sw2', '-sw2', type=float,  default=1, help='sw2')
parser.add_argument('--sw3', '-sw3', type=float,  default=1, help='sw3')
parser.add_argument('--sw4', '-sw4', type=float,  default=1, help='sw4')
parser.add_argument('--sw5', '-sw5', type=float,  default=1, help='sw5')
# parser for content weights
parser.add_argument('--cw1', '-cw1', type=float,  default=1, help='cw1')
parser.add_argument('--cw2', '-cw2', type=float,  default=1, help='cw2')
parser.add_argument('--cw3', '-cw3', type=float,  default=1, help='cw3')
parser.add_argument('--cw4', '-cw4', type=float,  default=1, help='cw4')
parser.add_argument('--cw5', '-cw5', type=float,  default=1, help='cw5')
# parser for cross entropy loss weights
parser.add_argument('--cew1', '-cew1', type=float,  default=1e5, help='cew1')
# parser for content class
parser.add_argument('--content_class', '-content_class', type=int, default=0, help='content class')
# parser for input images paths and names
parser.add_argument('--image_size', '-image_size', type=int, default=64)
# parser for input images paths and names
parser.add_argument('--serif_style_path', '-serif_style_path', type=str, default='input/4/style1_serif_A.png')
parser.add_argument('--nonserif_style_path', '-nonserif_style_path', type=str, default='input/4/style2_sanserif_A.png')
parser.add_argument('--content_path', '-content_path', type=str, default='input/4/4_content_sanserif_A.png')
# parser for output path
parser.add_argument('--output_path', '-output_path', type=str, default='./output/', help='Path to save output files')
# parser for cuda
parser.add_argument('--cuda', '-cuda', type=str, default='cuda:0', help='cuda:0 or cuda:x')

args = parser.parse_args()
#############################################################################
# Get image paths and names
# Style 1
style_dir1  = os.path.dirname(args.serif_style_path)
style_name1 = os.path.basename(args.serif_style_path)
# Style 2
style_dir2  = os.path.dirname(args.nonserif_style_path)
style_name2 = os.path.basename(args.nonserif_style_path)
# Content
content_dir  = os.path.dirname(args.content_path)
content_name = os.path.basename(args.content_path)

# Cuda device
if torch.cuda.is_available:
    device = args.cuda
else:
    device = 'cpu'
print("Using device: ", device)

# style weights
sw1=args.sw1
sw2=args.sw2
sw3=args.sw3
sw4=args.sw4
sw5=args.sw5
# Content weights
cw1=args.cw1
cw2=args.cw2
cw3=args.cw3
cw4=args.cw4
cw5=args.cw5
# Cross Entropy Loss weights
cew1=args.cew1
# Parameters
alpha = args.alpha
beta = args.beta
image_size = args.image_size
content_invert = False #1
style_invert = False #1
result_invert = content_invert
content_class = torch.unsqueeze(torch.tensor(args.content_class), dim=0)

# Get output path
n = str(len(glob(args.output_path + '*'))+1) + '/'
output_path = args.output_path + n
os.makedirs(output_path, exist_ok=True)

log_path = output_path + 'log.txt'
sys.stdout = Logger(log_path)

# Get network
# model = VGG()
# model.load_state_dict(torch.load('./vgg_conv.pth'))

# model = DISENTANGLE_MODEL(zdim=256, ch_num=26)
# model.load_state_dict(torch.load('./discentangle_model.pth'))
model = DISENTANGLE_MODEL2(zdim=256, ch_num=26)
model.load_state_dict(torch.load('./best_model_without_relu.pth', map_location='cuda:0'))

for param in model.parameters():
    param.requires_grad = False
model.to(device)
model.eval()

# Load images
content_image = load_images(os.path.join(content_dir, content_name), device)
style_image1  = load_images(os.path.join(style_dir1,style_name1), device)
style_image2  = load_images(os.path.join(style_dir2,style_name2), device)

# Random input
# opt_img = Variable(torch.randn(content_image.size()).type_as(content_image.data).to(device), requires_grad=True).to(device)
# Content input
opt_img = Variable(content_image.data.clone(), requires_grad=True)

# Define layers, loss functions, weights and compute optimization targets
# Style layers
# style_layers = ['r12','r22','r34','r44','r54'] # for vgg
style_layers = ['conv1', 'conv2', 'conv3', 'conv4'] # for discentangle model
# style_weights = [sw*1e3/n**2 for sw,n in zip([sw1,sw2,sw3,sw4,sw5],[64,128,256,512,1024])]
style_weights = [sw for sw in [sw1,sw2,sw3,sw4,sw5]]
# style_weights = [1,1,1,1,1]

# Content layers
# content_layers = ['r12','r22','r32','r42','r52']
# content_layers = ['r31','r32','r33','r34','r41']
# content_layers = ['r42'] # for vgg
content_layers = ['conv1'] # for discentangle model
# content_weights = [cw1*1e3]
content_weights = [cw1]
# content_weights = [cw1*1e4,cw2*1e4,cw3*1e4,cw4*1e4,cw5*1e4]

fms_layers = style_layers + content_layers
# loss_functions = [GramMSELoss()] * len(style_layers) + [nn.MSELoss()] * len(content_layers) + [nn.CrossEntropyLoss()] * len(cross_entropy_layers)
# loss_functions = [loss_fn.to(device) for loss_fn in loss_functions]
# weights = style_weights + content_weights


# Compute optimization targets
### Gram matrix targets

# Feature maps from style layers of the style images
style1_fms_style = [A.detach() for A in model(style_image1, style_layers)[0]]
style2_fms_style = [A.detach() for A in model(style_image2, style_layers)[0]]
# Gram matrices of style feature maps
style1_gramm = [GramMatrix()(A) for A in style1_fms_style]
style2_gramm = [GramMatrix()(A) for A in style2_fms_style]
# Difference between gram matrices of style1 and style2
gramm_style = [(style1_gramm[i] - style2_gramm[i]) for i in range(len(style_layers))]


# Difference between feature maps
#style_fms_style  = [style1_fms_style[i] - style2_fms_style[i] for i in range(len(style_layers))]
# Gram matrix of difference feature maps
#gramm_style = [GramMatrix()(A) for A in style_fms_style]


# Feature maps from style layers of the content image
content_fms_style = [A.detach() for A in model(content_image, style_layers)[0]]
content_gramm = [GramMatrix()(A) for A in content_fms_style]


### Content targets
# Feature maps from content layers of the style images
style1_fms_content = [A.detach() for A in model(style_image1, content_layers)[0]]
style2_fms_content = [A.detach() for A in model(style_image2, content_layers)[0]]
# Difference between feature maps
style_fms_content = [(style1_fms_content[i] - style2_fms_content[i]) for i in range(len(content_layers))]
# Feature maps from content layers of the content image
content_fms_content = [A.detach() for A in model(content_image, content_layers)[0]]

# Difference style and content feature
# class_feature_diff = model(style_image1, [])[1] - model(style_image1, [])[1]
font_feature_diff = model(style_image1, [])[2] - model(style_image2, [])[2]

_, content_class_feature, content_font_feature = model(content_image, [])

# Run style transfer
make_folders(output_path)

max_iter = 1000
show_iter = 100
optimizer = optim.LBFGS([opt_img], lr=1)
# optimizer = optim.Adam([opt_img], lr=1)
n_iter=[0]
loss_list = []
c_loss = []
s_loss = []
font_loss = []
class_loss = []

while n_iter[0] <= max_iter:

    def closure():
        # with torch.no_grad():
        # #     # _max = opt_img.max()
        # #     # _min = opt_img.min()
        # #     # opt_img = (opt_img - _min) / (_max - _min)
        #     opt_img.clamp_(0.0, 1.0)

        optimizer.zero_grad()

        out_feature, opt_class_feature, opt_font_feature = model(opt_img, fms_layers)

        # Divide between style feature maps and content feature maps
        opt_fms_style = out_feature[:len(style_layers)]
        opt_fms_content = out_feature[len(style_layers):]

        content_layer_losses = []
        style_layer_losses  = []

        ## Difference between feature maps on style layers
        # diff_fms_style = [opt_fms_style[i] - content_fms_style[i] for i in range(len(style_layers))]
        # gramm_diff = [GramMatrix()(A) for A in diff_fms_style]
        ## Difference between gram matrix of feature map differences
        # style_layer_losses = [style_weights[i]*(nn.MSELoss()(gramm_diff[i], gramm_style[i])) for i in range(len(style_layers))]

        opt_gramm = [GramMatrix()(A) for A in opt_fms_style]
        # Difference between gram matrices of content and opt
        gramm_diff = [(opt_gramm[i] - content_gramm[i]) for i in range(len(style_layers))]
        # MSE between (diff gram matrices style1,2) and (diff gram matrices opt, content)
        style_layer_losses = [style_weights[i]*nn.MSELoss()(gramm_diff[i], gramm_style[i]) for i in range(len(style_layers))]

        ## Difference between feature maps on content layers
        fms_diff = [(opt_fms_content[i] - content_fms_content[i]) for i in range(len(content_layers))]
        # MSE between (diff fms style1,2) and (diff fms opt, content)
        content_layer_losses = [content_weights[i]*nn.MSELoss()(fms_diff[i], style_fms_content[i]) for i in range(len(content_layers))]
        # content_layer_losses = [content_weights[i]*nn.MSELoss()(opt_fms_content[i],content_fms_content[i]) for i in range(len(content_layers))]

        # losses
        content_loss = sum(content_layer_losses)
        style_loss   = sum(style_layer_losses)
        font_feature_loss = nn.MSELoss()(font_feature_diff, opt_font_feature - content_font_feature)
        class_feature_loss = nn.MSELoss()(opt_class_feature, content_class_feature)

        # l1 norm
        l1 = torch.tensor(0., requires_grad=True)
        for p in opt_img:
            l1 = l1 +  torch.norm(1.0-p, 1)
        alpha = 0.0001

        loss = content_loss + style_loss + font_feature_loss + class_feature_loss #+ alpha*l1
        loss.backward()

        # ld1 = len(str(content_loss.item()))
        # ld2 = len(str(style_loss.item()))
        # if ld1 > ld2:
        #     div = ld1 - ld2
        #     style_loss = style_loss*(10**(div))
        # else:
        #     div = ld2 - ld1
        #     content_loss = content_loss*(10**(div))


        # for log
        c_loss.append(content_loss.item())
        s_loss.append(style_loss.item())
        font_loss.append(font_feature_loss.item())
        class_loss.append(class_feature_loss.item())
        loss_list.append(loss.item())

        #print loss
        if n_iter[0]%show_iter == 0:
            print('Iteration: {}'.format(n_iter[0]))
            if len(content_layers)>0: print('Content loss: {}'.format(content_loss.item()))
            if len(style_layers)>0: print('Style loss  : {}'.format(style_loss.item()))
            print('Font feature diff loss: {}'.format(font_feature_loss.item()))
            print('Class feature diff loss: {}'.format(class_feature_loss.item()))
            print('Total loss  : {}\n'.format(loss.item()))

            # Save loss graph
            plt.plot(loss_list, label='Total loss')
            if len(content_layers)>0:  plt.plot(c_loss, label='Content loss')
            if len(style_layers)>0:  plt.plot(s_loss, label='Style loss')
            plt.plot(font_loss, label='Font loss')
            plt.plot(class_loss, label='Class loss')
            plt.legend()
            plt.savefig(output_path + 'loss_graph.jpg')
            plt.close()
            # Save optimized image
            out_img = postp(opt_img.data[0].cpu(), image_size, result_invert)
            out_img.save(output_path + 'outputs/{}_pred.bmp'.format(n_iter[0]))

        n_iter[0] += 1
        return loss

    optimizer.step(closure)

# Save sum images
save_images(content_image.data[0].cpu().squeeze(), opt_img.data[0].cpu().squeeze(), style_image1.data[0].cpu().squeeze(), style_image2.data[0].cpu().squeeze(), image_size, output_path, n_iter, content_invert, style_invert, result_invert)
