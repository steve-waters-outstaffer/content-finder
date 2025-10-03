import React from 'react';
import { Box, Card, CardContent, Link, Typography } from '@mui/material';
import { CustomColors, FontWeight } from '../../theme';

const PostCard = ({ post, showAnalysis }) => (
    <Card variant="outlined" sx={{ mb: 2 }}>
        <CardContent sx={{ p: 2 }}>
            <Typography variant="subtitle1" fontWeight={FontWeight.Medium}>
                {post.title}
            </Typography>
            <Typography variant="caption" color="text.secondary">
                r/{post.subreddit} • Score {post.score} • {post.num_comments} comments
            </Typography>
            {post.content_snippet && (
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                    {post.content_snippet}
                </Typography>
            )}
            {showAnalysis && post.ai_analysis && (
                <Box sx={{ mt: 2, p: 2, bgcolor: CustomColors.UIGrey100, borderRadius: 1 }}>
                    <Typography variant="subtitle2" fontWeight={FontWeight.SemiBold} gutterBottom>
                        AI Insight
                    </Typography>
                    <Typography variant="body2">
                        <strong>Relevance:</strong> {post.ai_analysis.relevance_score ?? 'n/a'}
                    </Typography>
                    {post.ai_analysis.identified_pain_point && (
                        <Typography variant="body2" sx={{ mt: 0.5 }}>
                            <strong>Pain Point:</strong> {post.ai_analysis.identified_pain_point}
                        </Typography>
                    )}
                    {post.ai_analysis.reasoning && (
                        <Typography variant="body2" sx={{ mt: 0.5 }} color="text.secondary">
                            {post.ai_analysis.reasoning}
                        </Typography>
                    )}
                </Box>
            )}
            {post.url && (
                <Typography variant="body2" sx={{ mt: 1 }}>
                    <Link href={post.url} target="_blank" rel="noreferrer">
                        View discussion
                    </Link>
                </Typography>
            )}
        </CardContent>
    </Card>
);

export default PostCard;
