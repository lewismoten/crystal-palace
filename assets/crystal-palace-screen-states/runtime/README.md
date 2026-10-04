# Runtime presentation deltas

The files in this directory are generated, bounded presentation copies of the supplied title-player-one screen and colour planes. They preserve the original source planes in the parent directory unchanged.

Only four character cells differ: offsets `242`, `282`, `321`, and `322` (rows 6–8 in the left radar panel). Their screen and colour bytes are zero so the user-rejected `Y/4/4/7` glyphs render black from the first title frame. The build regression asserts that no other byte differs.
