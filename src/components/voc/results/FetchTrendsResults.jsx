import React from 'react';
import { Chip, Stack, Typography } from '@mui/material';
import { FontWeight } from '../../../theme';

const FetchTrendsResults = ({ stepInfo }) => {
    const trends = stepInfo?.data || [];

    return (
        <Stack spacing={2}>
            <Typography variant="h6" fontWeight={FontWeight.Medium}>
                Google Trends ({trends.length} keywords)
            </Typography>
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                {trends.map((trend) => (
                    <Chip key={trend.keyword} label={trend.keyword} />
                ))}
            </Stack>
        </Stack>
    );
};

export default FetchTrendsResults;
