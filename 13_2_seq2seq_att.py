# https://github.com/spro/practical-pytorch/blob/master/seq2seq-translation/seq2seq-translation.ipynb
import torch
import torch.nn as nn
from torch.autograd import Variable
from torch.utils.data import DataLoader
from text_loader import TextDataset
import seq2seq_models as sm
from seq2seq_models import cuda_variable, str2tensor, EOS_token, SOS_token


N_LAYERS = 1
BATCH_SIZE = 32
N_EPOCH = 100
N_CHARS = 128  # ASCII
HIDDEN_SIZE = N_CHARS


# Simple test to show how our train works
def test():
    encoder_test = sm.EncoderRNN(10, 10, 2)
    decoder_test = sm.AttnDecoderRNN('general', 10, 10, 2)

    if torch.cuda.is_available():
        encoder_test.cuda()
        decoder_test.cuda()

    encoder_hidden = encoder_test.init_hidden()
    word_input = cuda_variable(torch.LongTensor([1, 2, 3]))
    encoder_outputs, encoder_hidden = encoder_test(word_input, encoder_hidden)
    print(encoder_outputs.size())

    word_target = cuda_variable(torch.LongTensor([1, 2, 3]))
    decoder_attns = torch.zeros(1, 3, 3)
    decoder_hidden = encoder_hidden
    decoder_context = cuda_variable(torch.zeros(1, decoder_test.hidden_size))

    for c in range(len(word_target)):
        decoder_output, decoder_context, decoder_hidden, decoder_attn = \
            decoder_test(word_target[c], decoder_context,
                         decoder_hidden, encoder_outputs)
        print(decoder_output.size(), decoder_hidden.size(), decoder_attn.size())
        decoder_attns[0, c] = decoder_attn.squeeze(0).cpu().data


# Train for a given src and target
# To demonstrate seq2seq, We don't handle batch in the code,
# and our encoder runs this one step at a time
# It's extremely slow, and please do not use in practice.
# We need to use (1) batch and (2) data parallelism
# http://pytorch.org/tutorials/beginner/former_torchies/parallelism_tutorial.html.
def train(src, target):
    loss = 0

    src_var = str2tensor(src)
    target_var = str2tensor(target, eos=True)  # Add the EOS token

    encoder_hidden = encoder.init_hidden()
    encoder_outputs, encoder_hidden = encoder(src_var, encoder_hidden)

    hidden = encoder_hidden
    context = cuda_variable(torch.zeros(1, decoder.hidden_size))

    for c in range(len(target_var)):
        # First, we feed SOS. Others, we use teacher forcing.
        token = target_var[c - 1] if c else str2tensor(SOS_token)
        output, context, hidden, attention = decoder(
            token, context, hidden, encoder_outputs)
        loss += criterion(output, target_var[c])

    encoder.zero_grad()
    decoder.zero_grad()
    loss.backward()
    optimizer.step()

    return loss.data[0] / len(target_var)


# Translate the given input
def translate(enc_input='thisissungkim.iloveyou.', predict_len=100, temperature=0.9):
    input_var = str2tensor(enc_input)
    encoder_hidden = encoder.init_hidden()
    encoder_outputs, encoder_hidden = encoder(input_var, encoder_hidden)

    hidden = encoder_hidden
    context = cuda_variable(torch.zeros(1, decoder.hidden_size))

    predicted = ''
    dec_input = str2tensor(SOS_token)
    for c in range(predict_len):
        output, context, hidden, attention = \
            decoder(dec_input, context, hidden, encoder_outputs)
        # Sample from the network as a multi nominal distribution
        output_dist = output.data.view(-1).div(temperature).exp()
        top_i = torch.multinomial(output_dist, 1)[0]

        # Stop at the EOS
        if top_i is EOS_token:
            break

        predicted_char = chr(top_i)
        predicted += predicted_char

        dec_input = str2tensor(predicted_char)

    return enc_input, predicted


encoder = sm.EncoderRNN(N_CHARS, HIDDEN_SIZE, N_LAYERS)
decoder = sm.AttnDecoderRNN('general', HIDDEN_SIZE, N_CHARS, N_LAYERS)

if torch.cuda.is_available():
    decoder.cuda()
    encoder.cuda()
print(encoder, decoder)
# test()

params = list(encoder.parameters()) + list(decoder.parameters())
optimizer = torch.optim.Adam(params, lr=0.001)
criterion = nn.CrossEntropyLoss()


train_loader = DataLoader(dataset=TextDataset(),
                          batch_size=BATCH_SIZE,
                          shuffle=True,
                          num_workers=2)

print("Training for %d epochs..." % N_EPOCH)
for epoch in range(1, N_EPOCH + 1):
    # Get srcs and targets from data loader
    for i, (srcs, targets) in enumerate(train_loader):
        for src, target in zip(srcs, targets):
            train_loss = train(src, target)

        print('[(%d %d%%) %.4f]' %
              (epoch, epoch / N_EPOCH * 100, train_loss))
        print(translate(srcs[0]), '\n')
        print(translate(), '\n')
