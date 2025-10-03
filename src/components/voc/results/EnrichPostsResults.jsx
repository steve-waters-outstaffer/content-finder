import React from 'react';
import { Box, Chip, Stack, Typography } from '@mui/material';
import { CustomColors, FontWeight } from '../../../theme';
import PostCard from '../PostCard';

const EnrichPostsResults = ({ stepInfo }) => {
    const posts = stepInfo?.data || [];
    const stats = stepInfo?.stats;
    const threshold = stepInfo?.threshold ?? 0;

    return (
        <Box>
            <Typography variant="h6" fontWeight={FontWeight.Medium} gutterBottom>
                Enriched Posts with Deep Analysis
            </Typography>

            {stats && (
                <Stack direction="row" spacing={2} sx={{ mb: 3 }}>
                    <Chip label={`${stats.input} Input Posts`} sx={{ bgcolor: CustomColors.UIGrey400 }} />
                    <Chip
                        label={`${stats.final_accepted} Final Accepted (≥${threshold})`}
                        sx={{ bgcolor: CustomColors.SecretGarden + '20' }}
                    />
                    <Chip label={`${stats.final_rejected} Rejected`} sx={{ bgcolor: CustomColors.UIGrey300 }} />
                </Stack>
            )}

            <Box sx={{ maxHeight: 600, overflow: 'auto' }}>
                {posts.map((post) => (
                    <PostCard key={post.id} post={post} showAnalysis />
                ))}
            </Box>
        </Box>
    );
};

export default EnrichPostsResults;
