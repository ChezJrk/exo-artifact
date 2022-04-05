from __future__ import annotations
import pytest
from exo.platforms.gemmini import *
from exo.platforms.harness_gemmini import GemmTestBuilder


def conv_algorithm():
    @proc
    def conv(
        batch_size : size,
        out_dim    : size,
        out_channel: size,
        kernel_dim : size,
        in_channel : size,
        in_dim     : size,
        output     : i8[batch_size, out_dim, out_dim, out_channel],
        bias       : i32[1,out_channel],
        inp        : i8[batch_size, in_dim, in_dim, in_channel],
        weights    : i8[kernel_dim, kernel_dim, in_channel, out_channel],
        act        : bool,
        scale      : f32
        ):

        assert out_dim == in_dim - kernel_dim + 1

        # Algorithm starts here
        for b in par(0, batch_size):
            for orow in par(0, out_dim):
                for ocol in par(0, out_dim):
                    for och in par(0, out_channel):

                        res : i32
                        res = bias[0,och]
                        for krow in par(0, kernel_dim):
                            for kcol in par(0, kernel_dim):
                                for kch in par(0, in_channel):
                                    w_s : i8 @ DRAM
                                    w_s = weights[krow,kcol,kch,och]

                                    i_s : i8 @ DRAM
                                    i_s = inp[b,orow+krow,ocol+kcol,kch]

                                    a2 : i32
                                    b2 : i32
                                    a2 = i_s
                                    b2 = w_s

                                    res += a2 * b2

                        src_tmp : i32
                        src_tmp = res
                        tmp_res1 : f32
                        acc_scale(src_tmp, tmp_res1, scale)
                        tmp_res2 : i8
                        clamp(tmp_res1, tmp_res2)
                        if act == True:
                            tmp_res2 = relu(tmp_res2)

                        output[b,orow,ocol,och] = tmp_res2
        # Algorithm ends here. 26 lines excluding newlines

    return conv


# Conv test for the artifact evaluation. The same algorithm and schedule
# was used for Table 2 (first row) and Table 3 (code size)
def test_conv_ae():
    batch_size = 4
    out_channel= 64
    kernel_dim = 3
    in_channel = 64
    in_dim     = 58
    out_dim    = int((in_dim - kernel_dim)/1 + 1)
    assert out_dim == 56

    # These lines are relevant if you have GEMMINI environment set up
    T = GemmTestBuilder('conv_ae')
    T.add_body(['gemm_init_mem();',
                'gemm_acc_init_mem();',
                'gemmini_flush(0);',
                ''])
    T.add_body(["conv_ae_lib_Context *ctxt;"])

    T.alloc_dram_f32('scale', '1.0')
    T.alloc_dram_2i32('bias', 1, out_channel, '-1*j')
    T.alloc_dram_4i8('output_cpu', batch_size, out_dim, out_dim, out_channel, '0')
    T.alloc_dram_4i8('output_gemmini', batch_size, out_dim, out_dim, out_channel, '0')
    T.alloc_dram_4i8('inp', batch_size, in_dim, in_dim, in_channel, 'j+k+r*3')
    T.alloc_dram_4i8('weights', out_channel, kernel_dim, kernel_dim, in_channel, 'i+k*3+r')

    # Rename the conv algorithm to "conv_on_gemmini"
    gemmini = conv_algorithm().rename("conv_on_gemmini")

    print("")
    print("===== THIS IS THE CONV ALGORITHM BEFORE SCHEDULING ====")
    print(gemmini)
    print("===== THIS IS THE CONV ALGORITHM BEFORE SCHEDULING ====")
    print("")

    # Schedule starts here. Below schedule partially evaluates the proc with conv parameters
    gemmini = gemmini.partial_eval(batch_size, out_dim, out_channel, kernel_dim, in_channel, in_dim)

    # Split the outer dimension and replace the code with gemmini instructions
    gemmini = split_fission_dim(gemmini)
    gemmini = replace_div_part(gemmini)
    gemmini = replace_mod_part(gemmini)

    # Set buffers to use gemmini memories
    gemmini = gemmini.set_memory('res', GEMM_ACCUM)
    gemmini = gemmini.set_memory('i_s', GEMM_SCRATCH)
    gemmini = gemmini.set_memory('w_s', GEMM_SCRATCH)

    # Inline and lift the configuration as high as possible for the "div" part
    gemmini = inline_vector(gemmini)
    gemmini = lift_config(gemmini, 'config_ld_acc_i32_vector(_)')
    gemmini = inline_ld_id1(gemmini)
    gemmini = lift_config(gemmini, 'config_ld_i8_id1(_)')
    gemmini = inline_matmul(gemmini)
    gemmini = lift_config(gemmini, 'config_matmul(_)')
    gemmini = inline_st(gemmini)
    gemmini = lift_config(gemmini, 'config_st_acc_i8(_)')

    # Inline and lift the configuration as high as possible for the "mod" part (tail case)
    gemmini = inline_vector(gemmini)
    gemmini = inline_ld_id1(gemmini)
    gemmini = inline_matmul(gemmini)
    gemmini = inline_st(gemmini)
    gemmini = gemmini.delete_config("config_ld_acc_i32_vector(_) #1")
    gemmini = gemmini.delete_config("config_ld_i8_id1(_) #1")
    gemmini = gemmini.delete_config("config_matmul(_) #1")
    gemmini = gemmini.delete_config("config_st_acc_i8(_) #1")
    gemmini = gemmini.simplify()

    # Real optimization
    gemmini = gemmini.lift_alloc('w_s : _', n_lifts=2)
    gemmini = gemmini.fission_after('for ocol_o in _:_ #0')
    gemmini = gemmini.reorder('orow', 'ocol_o')
    gemmini = gemmini.split('orow', 28, ['orow_o', 'orow_i'], perfect=True)
    gemmini = gemmini.expand_dim('i_s: i8[_]', '30', 'krow + orow_i', unsafe_disable_checks=True)
    [ (gemmini := gemmini.par_to_seq(s)) for s in ['for krow in _:_', 'for b in _:_', 'for orow_o in _:_', 'for orow_i in _:_', 'for ocol_o in _:_'] ]
    gemmini = gemmini.lift_alloc('i_s : _', n_lifts=5)
    gemmini = gemmini.lift_alloc('w_s : _', n_lifts=4)

    [ (gemmini := gemmini.add_guard(s, i, 0)) for (s,i) in [('for kch_o in _:_', 'ocol_o'), ('for kch_o in _:_', 'b'), ('for kch_o in _:_ #2', 'b'), ('for kch_o in _:_', 'orow_o'), ('for kch_o in _:_', 'orow_i'), ('for kch_o in _:_ #2', 'orow_o #1'), ('for kch_o in _:_ #2', 'orow_i #1')] ]
    gemmini = gemmini.add_unsafe_guard('ld_i8_block_id2(_) #0', 'orow_i == 0 or krow == 2')
    gemmini = gemmini.add_unsafe_guard('ld_i8_block_id2(_) #1', 'orow_i == 0 or krow == 2')

    gemmini = gemmini.split('orow_i', 7, ['orow_io', 'orow_ii'], perfect=True)
    gemmini = gemmini.lift_alloc('res : _', n_lifts=1)
    gemmini = gemmini.par_to_seq('for orow_io in _:_')
    gemmini = gemmini.lift_alloc('res : _', n_lifts=4)
    gemmini = gemmini.unroll('och_o')
    gemmini = gemmini.unroll('kch_o')
    gemmini = gemmini.unroll('kcol')
    gemmini = gemmini.unroll('krow')
    gemmini = gemmini.simplify()

    # Schedule ends here, 44 lines excluding comments and newlines


    cpu = conv_algorithm().rename("conv_on_cpu")
    cpu = cpu.partial_eval(batch_size, out_dim, out_channel, kernel_dim, in_channel, in_dim)

    # These lines are relevant if you want to run the generated C code with GEMMINI simulator
    T.add_proc(cpu)
    T.add_proc(gemmini)

    T.start_timer('cpu')

    T.add_body([f'conv_on_cpu(ctxt, output_cpu, bias, inp, weights, false, scale);',
                f'gemmini_fence();'])
    T.stop_timer('cpu', 'Cycles for CPU version')

    T.start_timer('gemmini')
    T.add_body([f'conv_on_gemmini(ctxt, output_gemmini, bias, inp, weights, false, scale);',
                f'gemmini_fence();'])
    T.stop_timer('gemmini', 'Cycles for GEMMINI version')

    T.add_body([f'if(check_eq_4i8({batch_size},{out_dim},{out_dim},{out_channel}, output_cpu, output_gemmini)) {{',
                 '    printf("Correct\\n");',
                 '} else {',
                 '    printf("Results Don\'t Match\\n");',
                 '    printf("Correct Result (output_cpu):\\n");',
                f'    print_4i8({batch_size},{out_dim},{out_dim},{out_channel}, output_cpu);',
                 '    printf("Computed Roundtrip (output_gemmini):\\n");',
                f'    print_4i8({batch_size},{out_dim},{out_dim},{out_channel}, output_gemmini);',
                 '    exit(1);',
                 '}',
                 ''])

    T.compile().run()


    print("")
    print("============= THIS IS THE SCHEDULED CONV ===============")
    print(gemmini)
    print("============= THIS IS THE SCHEDULED CONV ===============")
    print("")
