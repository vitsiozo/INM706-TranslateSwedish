import torch
from torch.utils.data import DataLoader, TensorDataset
#from torchtext.data.metrics import bleu_score # changed from bleu_score
from nltk.translate.bleu_score import sentence_bleu
from transformers import MarianTokenizer
from model import Encoder, Decoder, Seq2Seq
from utils import collate_fn2, decode_tokens, parse_arguments, read_settings

import sacrebleu
#Setting the device 
device = torch.device('mps' if torch.backends.mps.is_available() else ('cuda' if torch.cuda.is_available() else 'cpu'))
print('Device set to {0}'.format(device))

# Read config settings
args = parse_arguments()
settings = read_settings(args.config)
config = settings['model_settings']

tokenizer = MarianTokenizer.from_pretrained('./opus-mt-en-sv')

num_token_id = tokenizer.convert_tokens_to_ids('<num>')
if num_token_id == tokenizer.unk_token_id:  # Checking if <num> is recognized , they should be equal id since above convertion makes <num> as unk
    tokenizer.add_tokens(['<num>'])
    #print("Added <num> with ID:", tokenizer.convert_tokens_to_ids('<num>'))

#Inlcude bos id 
if tokenizer.bos_token_id is None:
    tokenizer.add_special_tokens({'bos_token': '<s>'})
    #print("Added <bos> with ID:", tokenizer.convert_tokens_to_ids('<bos>'))

print('Showing the special tokens of the tokenizer:',tokenizer.special_tokens_map)
print(f'eos_id:',tokenizer.eos_token_id,'bos_id:',tokenizer.bos_token_id,'pad_id:', tokenizer.pad_token_id, 'unk_id:',tokenizer.unk_token_id)

print('Tokenizer vocab size:',tokenizer.vocab_size)
vocab_size = len(tokenizer.get_vocab())
print("Updated tokenizer vocab size:", vocab_size) #This one should be used

# Load test data
test_data = torch.load('test_data_seq.pth')
test_loader = DataLoader(test_data, config['batch_size'],collate_fn=collate_fn2, shuffle=False)

encoder = Encoder(vocab_size,300,1024,2,0.5)
decoder = Decoder(vocab_size,300,1024,2,0.5)
model = Seq2Seq(encoder, decoder, device).to(device)
model.load_state_dict(torch.load('models/seq-model.pth', map_location=torch.device('cpu')))

def calculate_bleu(test_loader, model, tokenizer, device):

    model.eval()
    reference = []
    candidate = []
    overall_score = 0
    with torch.no_grad():
        for batch in test_loader:
            input_ids, labels, attention_mask = batch
            input_ids,labels = input_ids.to(device), labels.to(device)
            #print(input_ids, labels)

            #Forward pass 
            outputs= model(input_ids,labels,0)
            outputs =outputs.argmax(-1)

            predictions = [tokenizer.decode(ids, skip_special_tokens=True) for ids in outputs]
            actuals = [tokenizer.decode(ids, skip_special_tokens=True) for ids in labels]

            # Extend the output_texts list instead of the output_tensor
            candidate =[pred.split() for pred in predictions]
            reference = [tgt.split() for tgt in actuals]
            #Make reference list of list
            #reference = [reference]    
            #print(reference)
            #print(candidate)

            candidate = [' '.join(pred.split()) for pred in predictions]
            reference = [[' '.join(tgt.split())] for tgt in actuals]
            # Calculate the BLEU score for each candidate and reference pair
            scores = [sacrebleu.raw_corpus_bleu([cand], [ref]).score for cand, ref in zip(candidate, reference)]
            average_score = sum(scores) / len(scores)
            overall_score += average_score

    print(overall_score / len(test_loader))
    return overall_score / len(test_loader)
            #break
            #for pred, act in zip(predictions, actuals):
            #    print(f'Prediction: {pred} \nActual: {act}\n')

if __name__ == '__main__':
    bleu_score = calculate_bleu(test_loader, model, tokenizer, device)
    print(f"Calculated BLEU Score: {bleu_score:.2f}%")