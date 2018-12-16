python3 train_model.py --train "../data/eng_train.txt" \
--valid "../data/eng_testa.txt" \
--test "../data/eng_testb.txt" \
--wvp "../data/word_vocab.pkl" \
--cvp "../data/char_vocab.pkl" \
--tvp "../data/tag_vocab.pkl" \
--embedding glove \
--clpw 12 \
--nce 30 \
--nwe 100 \
--nf 30 \
--ks 3 \
--nhiddens 256 \
--nlayers 1 \
--nts 128 \
--edp 0.33 \
--odp 0.33 \
--rdp 0.33 0.5 \
--nepochs 200 \
--lr 0.01 \
--bc 16 \
--lds 1 \
--ldr 0.05 \
--op_name sgd \
--lp "../data/eval_files/logs.log"
