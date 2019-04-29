import os
from tqdm import tqdm
import numpy as np

import torch
import torch.optim as optim
import torch.cuda
import torchvision
import torchvision.transforms as transforms
from torch.utils.data.sampler import SubsetRandomSampler

from GraphDecompositionBO.config import data_directory
from GraphDecompositionBO.experiments.NAS_binary.generate_architecture import valid_net_topo, NASBinaryCNN

from GraphDecompositionBO.experiments.NAS_binary.config_cifar10 import NORM_MEAN, NORM_STD
from GraphDecompositionBO.experiments.exp_utils import sample_init_points


N_VALID = 10000


def load_cifar10(batch_size, shuffle, random_seed=None):
	num_workers = 0
	transform = transforms.Compose([transforms.ToTensor(), transforms.Normalize(mean=NORM_MEAN, std=NORM_STD)])
	data_dir = os.path.join(data_directory(), 'CIFAR10')

	train_data = torchvision.datasets.CIFAR10(root=data_dir, train=True, download=True, transform=transform)
	test_data = torchvision.datasets.CIFAR10(root=data_dir, train=False, download=True, transform=transform)
	indices = list(range(len(train_data)))
	if shuffle:
		np.random.RandomState(random_seed).shuffle(indices)
	train_idx, valid_idx = indices[:-N_VALID], indices[-N_VALID:]
	train_sampler = SubsetRandomSampler(train_idx)
	valid_sampler = SubsetRandomSampler(valid_idx)

	train_loader = torch.utils.data.DataLoader(train_data, batch_size=batch_size, sampler=train_sampler,
	                                           num_workers=num_workers)
	valid_loader = torch.utils.data.DataLoader(train_data, batch_size=batch_size, sampler=valid_sampler,
	                                           num_workers=num_workers)
	test_loader = torch.utils.data.DataLoader(test_data, batch_size=batch_size, shuffle=False, num_workers=num_workers)

	return train_loader, valid_loader, test_loader


def train(model, n_epochs, train_loader, eval_loader, cuda=False):
	cuda = torch.cuda.is_available() and cuda

	if cuda:
		model.cuda()

	eval_acc_list = []

	criterion = torch.nn.CrossEntropyLoss()
	optimizer = optim.Adam(model.parameters(), weight_decay=5e-5)

	for epoch in range(n_epochs):
		running_loss = 0.0
		i_range = tqdm(range(len(train_loader)))
		for i, train_data in zip(i_range, train_loader):
			train_inputs, train_labels = train_data
			if cuda:
				train_inputs = train_inputs.cuda()
				train_labels = train_labels.cuda()

			optimizer.zero_grad()

			train_outputs = model(train_inputs)
			train_loss = criterion(train_outputs, train_labels)
			train_loss.backward()
			optimizer.step()

			running_loss += train_loss.item()
			i_range.refresh()
		i_range.close()

		eval_loss_sum = 0
		eval_acc_sum = 0
		for eval_data in eval_loader:
			eval_inputs, eval_labels = eval_data
			if cuda:
				eval_inputs = eval_inputs.cuda()
				eval_labels = eval_labels.cuda()
			eval_outputs = model(eval_inputs).detach()
			eval_loss = criterion(eval_outputs, eval_labels)
			eval_pred = torch.argmax(eval_outputs, dim=1)
			eval_loss_sum += eval_loss
			eval_acc_sum += torch.sum(eval_pred == eval_labels)
		eval_loss_avg = eval_loss_sum.item() / float(len(eval_loader.sampler))
		eval_acc_avg = eval_acc_sum.item() / float(len(eval_loader.sampler))

		eval_acc_list.append(eval_acc_avg)

		print('%4d epoch Train running loss: %.3f / Eval Avg. loss: %.3f / Eval Avg. Acc.: %5.2f%%'
		      % (epoch + 1, running_loss / 2000, eval_loss_avg, eval_acc_avg * 100))
	return np.max(eval_acc_avg)


class NASBinaryCIFAR10(object):
	def __init__(self, random_seed):
		self.n_nodes = 7
		self.n_binary = int(self.n_nodes * (self.n_nodes - 1) / 2 + (self.n_nodes - 2) * 2)
		self.n_ch_base = 64
		self.n_epochs = 20
		self.train_loader, self.valid_loader, _ = load_cifar10(batch_size=64, shuffle=True, random_seed=0)

		self.n_vertices = np.array([2] * self.n_binary)
		self.suggested_init = sample_init_points(self.n_vertices, 20, random_seed)

	def evaluate(self, x):
		assert x.numel() == self.n_binary
		if x.dim() == 2:
			x = x.squeeze(0)
		x_np = (x.cpu() if x.is_cuda else x).numpy().astype(np.int)
		node_type = x_np[:2 * (self.n_nodes - 2)]
		connectivity = x_np[2 * (self.n_nodes - 2):]
		adj_mat = np.zeros((self.n_nodes, self.n_nodes))
		ind = 0
		for i in range(self.n_nodes):
			adj_mat[i, i+1:] = connectivity[ind:ind + (self.n_nodes - i - 1)]
			ind = ind + (self.n_nodes - i - 1)
		adj_mat = valid_net_topo(adj_mat)
		# An improperly trained model will have approximately 10% accuracy on a balanced 10-classes problem.
		if adj_mat is None:
			return -0.1 * x.float().new_ones(1, 1)
		model = NASBinaryCNN(node_type, adj_mat, n_ch_base=self.n_ch_base)
		n_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
		neg_eval_acc = -train(model, self.n_epochs, self.train_loader, self.valid_loader, cuda=True)
		eval = neg_eval_acc + n_params / 500000000.0
		print(neg_eval_acc, n_params / 500000000.0)
		return eval * x.float().new_ones(1, 1)


if __name__ == '__main__':
	nas_binary_ = NASBinaryCIFAR10(random_seed=0)
	x_ = torch.randint(0, 2, (nas_binary_.n_binary, ))
	print(nas_binary_.evaluate(x_))