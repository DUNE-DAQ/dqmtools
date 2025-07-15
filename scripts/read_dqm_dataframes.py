#!/usr/bin/env python3

import pandas as pd

import click


@click.command()
@click.argument('input_filenames', nargs=-1, type=click.Path(exists=True))
def main(input_filenames):
    df_dict = {}

    for filename in input_filenames:
        print(f'Processing file {filename}.')

        with pd.HDFStore(filename, 'r') as store:

            # Loop through each key
            for key in store.keys():
                my_key = key[1:]  # remove front '/'
                if my_key not in df_dict:
                    df_dict[my_key] = []
                df_dict[my_key].append(store[key])

    for key in df_dict.keys():
        df_dict[key] = pd.concat(df_dict[key])

    print(f'Files contained {len(df_dict.keys())} keys.')
    for key, df in df_dict.items():
        print(f'\tDataframe name: {key}')
        print(f'\t\tTotal entries: {len(df)}')
        print(f'\t\tDataframe indices: {df.index.names}')
        print(f'\t\tDataframe columns: {df.columns.to_list()}')


if __name__ == '__main__':
    main()
