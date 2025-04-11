<?php
if (!defined('ABSPATH')) {
    exit;
}

/**
 * 處理 REST API 中的自訂欄位更新
 */
function handle_video_meta_update($post, $request) {
    if ($post->post_type !== 'video') {
        return $post;
    }

    $params = $request->get_params();
    
    // 更新 video_url (Media Id)
    if (isset($params['meta']['video_url'])) {
        update_post_meta($post->ID, 'video_url', sanitize_text_field($params['meta']['video_url']));
    }

    // 更新 length (Video Length) - 保留所有必要的欄位名稱
    $length_value = null;
    
    // 從 meta 中檢查 length
    if (isset($params['meta'])) {
        if (isset($params['meta']['length'])) {
            $length_value = $params['meta']['length'];
        }
    }

    // 如果找到值，更新所有需要的欄位名稱
    if ($length_value !== null) {
        $length_value = sanitize_text_field($length_value);
        update_post_meta($post->ID, 'length', $length_value);
        update_post_meta($post->ID, '_length', $length_value);
        update_post_meta($post->ID, 'video_length', $length_value);
    }

	// 處理 text_tracks
    if (isset($params['meta']['text_tracks'])) {
        update_post_meta($post->ID, 'text_tracks', $params['meta']['text_tracks']);
    }
    return $post;
}
add_action('rest_insert_video', 'handle_video_meta_update', 10, 2);

/**
 * 在 REST API 回應中添加自訂欄位
 */
function add_video_meta_to_rest_api($response, $post, $request) {
    if ($post->post_type !== 'video') {
        return $response;
    }

    if (!isset($response->data['meta'])) {
        $response->data['meta'] = array();
    }

    // 獲取 video_url
    $video_url = get_post_meta($post->ID, 'video_url', true);
    
    // 獲取 length - 依序檢查所有可能的欄位名稱
    $length = get_post_meta($post->ID, 'length', true);
    if (!$length) {
        $length = get_post_meta($post->ID, '_length', true);
    }
    if (!$length) {
        $length = get_post_meta($post->ID, 'video_length', true);
    }

	// 獲取 text_tracks
    $text_tracks = get_post_meta($post->ID, 'text_tracks', true);
	
    $response->data['meta']['video_url'] = $video_url;
    $response->data['meta']['length'] = $length;
	$response->data['meta']['text_tracks'] = $text_tracks;

    return $response;
}
add_filter('rest_prepare_video', 'add_video_meta_to_rest_api', 10, 3);

/**
 * 註冊 REST API 欄位
 */
function register_video_meta_fields() {
    // 註冊 video_url
    register_meta('post', 'video_url', array(
        'object_subtype' => 'video',
        'show_in_rest' => true,
        'single' => true,
        'type' => 'string',
        'auth_callback' => function() {
            return current_user_can('edit_posts');
        }
    ));

    // 註冊所有需要的 length 欄位
    $length_fields = array('length', '_length', 'video_length');
    foreach ($length_fields as $field) {
        register_meta('post', $field, array(
            'object_subtype' => 'video',
            'show_in_rest' => true,
            'single' => true,
            'type' => 'string',
            'auth_callback' => function() {
                return current_user_can('edit_posts');
            }
        ));
    }
	
	 // 註冊 text_tracks 欄位
    register_meta('post', 'text_tracks', array(
        'object_subtype' => 'video',
        'show_in_rest' => true,
        'single' => true,
        'type' => 'object', // 因為它包含多個欄位
        'description' => 'Text tracks for subtitles',
        'sanitize_callback' => 'wp_unslash', // 根據需要調整
        'auth_callback' => function() {
            return current_user_can('edit_posts');
        }
    ));
}
