from __future__ import print_function

import argparse
import imageio
from model_eager import PSPNet50
from tools import *

ADE20k_param = {'crop_size': [473, 473],
                'num_classes': 150}

SAVE_DIR = './output/'
CHECKPOINT_FILE = './checkpoint.npy'

def get_arguments():
    parser = argparse.ArgumentParser(description="Reproduced PSPNet")
    parser.add_argument("--img-path", type=str, default='',
                        help="Path to the RGB image file.")
    parser.add_argument("--checkpoints", type=str, default=CHECKPOINT_FILE,
                        help="Path to restore weights.")
    parser.add_argument("--save-dir", type=str, default=SAVE_DIR,
                        help="Path to save output.")
    parser.add_argument("--flipped-eval", action="store_true",
                        help="whether to evaluate with flipped img.")
    return parser.parse_args()


def main():
    args = get_arguments()

    # load parameters
    param = ADE20k_param

    crop_size = param['crop_size']
    num_classes = param['num_classes']

    # preprocess images
    img, filename = load_img(args.img_path)
    img = tf.expand_dims(img, 0)
    img_shape = tf.shape(img)
    h, w = (tf.maximum(crop_size[0], img_shape[1]), tf.maximum(crop_size[1], img_shape[2]))
    img = preprocess_eager(img, h, w)     # input if args.flipped-eval false
    flipped_img = tf.image.flip_left_right(tf.squeeze(img))
    flipped_img = tf.expand_dims(flipped_img, 0)        # input if args.flipped-eval true

    # Create network.
    net = PSPNet50(num_classes=num_classes, checkpoint_npy_path=args.checkpoints)
    net.trainable = False
    if args.flipped_eval:
        net2 = PSPNet50(num_classes=num_classes,checkpoint_npy_path=args.checkpoints)

    raw_output = net.predict_on_batch(img)

    # Do flipped eval or not
    if args.flipped_eval:
        flipped_output = tf.image.flip_left_right(tf.squeeze(net2.predict_on_batch(flipped_img)))
        flipped_output = tf.expand_dims(flipped_output, dim=0)
        raw_output = tf.add_n([raw_output, flipped_output])

    # Predictions.
    raw_output_up = tf.image.resize(raw_output, size=[h, w])
    raw_output_up = tf.image.crop_to_bounding_box(raw_output_up, 0, 0, img_shape[1], img_shape[2])
    raw_output_up = tf.argmax(raw_output_up, axis=3)
    pred = decode_labels_eager(raw_output_up, img_shape, num_classes)

    if not os.path.exists(args.save_dir):
        os.makedirs(args.save_dir)
    imageio.imwrite(args.save_dir + filename, pred[0])
    # Save labels of pixels
    np.save(args.save_dir + '/'+ filename + '_label_matrix.npy', raw_output_up)

if __name__ == '__main__':
    main()