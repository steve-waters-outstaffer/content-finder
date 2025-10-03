import React from 'react';
import { Stack, Typography } from '@mui/material';
import { FontWeight } from '../../../theme';

const GenerateQueriesResults = ({ stepInfo }) => {
    const queries = stepInfo?.data || [];

    return (
        <Stack spacing={2}>
            <Typography variant="h6" fontWeight={FontWeight.Medium}>
                Curated Research Prompts ({queries.length})
            </Typography>
            <Stack spacing={1} sx={{ mt: 2 }}>
                {queries.map((query, idx) => (
                    <Typography key={idx} variant="body2">
                        • {query}
                    </Typography>
                ))}
            </Stack>
        </Stack>
    );
};

export default GenerateQueriesResults;
