from __future__ import print_function

import argparse
import imageio
from model_graph import PSPNet50
from tools import *

ADE20k_param = {'crop_size': [473, 473],
                'num_classes': 150, 
                'model': PSPNet50}

SAVE_DIR = 'output/'
SNAPSHOT_DIR = 'checkpoint/'

def get_arguments():
    parser = argparse.ArgumentParser(description="Reproduced PSPNet")
    parser.add_argument("--img-path", type=str, default='',
                        help="Path to the RGB image file.")
    parser.add_argument("--checkpoints", type=str, default=SNAPSHOT_DIR,
                        help="Path to restore weights.")
    parser.add_argument("--save-dir", type=str, default=SAVE_DIR,
                        help="Path to save output.")
    parser.add_argument("--flipped-eval", action="store_true",
                        help="whether to evaluate with flipped img.")

    return parser.parse_args()

def save(saver, sess, logdir, step):
   model_name = 'model.ckpt'
   checkpoint_path = os.path.join(logdir, model_name)

   if not os.path.exists(logdir):
      os.makedirs(logdir)
   saver.save(sess, checkpoint_path, global_step=step)
   print('The checkpoint has been created.')

def load(saver, sess, ckpt_path):
    saver.restore(sess, ckpt_path)
    print("Restored model parameters from {}".format(ckpt_path))

def main():
    args = get_arguments()

    # disable eager execution
    tf.compat.v1.disable_eager_execution()

    # load parameters
    param = ADE20k_param

    crop_size = param['crop_size']
    num_classes = param['num_classes']
    PSPNet = param['model']

    # preprocess images
    img, filename = load_img(args.img_path)
    img_shape = tf.shape(img)
    h, w = (tf.maximum(crop_size[0], img_shape[0]), tf.maximum(crop_size[1], img_shape[1]))
    img = preprocess(img, h, w)

    # Create network.
    net = PSPNet({'data': img}, is_training=False, num_classes=num_classes)
    with tf.compat.v1.variable_scope('', reuse=True):
        flipped_img = tf.image.flip_left_right(tf.squeeze(img))
        flipped_img = tf.expand_dims(flipped_img, 0)
        net2 = PSPNet({'data': flipped_img}, is_training=False, num_classes=num_classes)

    raw_output = net.layers['conv6']
    
    # Do flipped eval or not
    if args.flipped_eval:
        flipped_output = tf.image.flip_left_right(tf.squeeze(net2.layers['conv6']))
        flipped_output = tf.expand_dims(flipped_output, dim=0)
        raw_output = tf.add_n([raw_output, flipped_output])

    # Predictions.
    raw_output_up = tf.compat.v1.image.resize_bilinear(raw_output, size=[h, w], align_corners=True)
    raw_output_up = tf.image.crop_to_bounding_box(raw_output_up, 0, 0, img_shape[0], img_shape[1])
    raw_output_up_print = tf.argmax(raw_output_up, axis=3)
    pred = decode_labels(raw_output_up_print, img_shape, num_classes)

    # Init tf Session
    config = tf.compat.v1.ConfigProto()
    config.gpu_options.allow_growth = True
    sess = tf.compat.v1.Session(config=config)
    init = tf.compat.v1.global_variables_initializer()

    sess.run(init)

    restore_var = tf.compat.v1.global_variables()

    ckpt = tf.train.get_checkpoint_state(args.checkpoints)
    if ckpt and ckpt.model_checkpoint_path:
        loader = tf.compat.v1.train.Saver(var_list=restore_var)
        load(loader, sess, ckpt.model_checkpoint_path)
    else:
        print('No checkpoint file found.')
    
    label_matrix, preds = sess.run([raw_output_up_print, pred])

    # f = open("global_variables_graph_mode.txt", "w")
    # print(tf.compat.v1.global_variables(),file=f)

    if not os.path.exists(args.save_dir):
        os.makedirs(args.save_dir)
    imageio.imwrite(args.save_dir + filename, preds[0])
    # Save labels of pixels
    img_name = filename.split('.')[0]
    np.save(args.save_dir+'/'+img_name+'_label_matrix.npy', label_matrix)

if __name__ == '__main__':
    main()
