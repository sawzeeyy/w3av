import sys


def write_output(output_stream, output):
    if output_stream is None:
        sys.exit(0)
    else:
        output_stream.write('\n'.join(output))
        output_stream.write('\n')
        output_stream.flush()
