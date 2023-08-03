#  Copyright 2023 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import os
import boto3
import json
import datetime
from backend.common.validators import validate

dynamodb = boto3.resource("dynamodb")
s3c = boto3.client("s3")

response = {
    "statusCode": 200,
    "body": "",
    "headers": {
        "Content-Type": "application/json",
        "Access-Control-Allow-Credentials": True,
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Allow-Methods": "OPTIONS,POST,GET",
    },
}

comment_database = None

try:
    comment_database = os.environ["COMMENT_STORAGE_TABLE_NAME"]
except:
    print("Failed Loading Environment Variables")
    response["statusCode"] = 500
    response["body"] = json.dumps({"message": "Failed Loading Environment Variables"})


def add_comment(assetId: str, assetVersionIdAndCommentId: str, event: dict) -> dict:
    """
    Creates the JSON for a comment based on the parameters and adds the comment to the database
    :param assetId: string containing the assetId that the comment will be attached to
    :param assetVersionIdAndCommentId: string with the asset version id the comment will be attached to and the unique comment id
    :param event: Lambda event dictionary
    :returns: dictionary with status code and success info
    """
    response = {"statusCode": 200, "message": "Succeeded"}
    print("Setting Table")
    print(comment_database)
    table = dynamodb.Table(comment_database)
    print("Setting Time Stamp")
    dtNow = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    print("current time in ISO8601:" + dtNow)
    item = {
        "assetId": assetId,
        "assetVersionId:commentId": assetVersionIdAndCommentId,
        "commentBody": event["body"]["commentBody"],
        "commentOwnerID": event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"],
        "commentOwnerUsername": event["requestContext"]["authorizer"]["jwt"]["claims"][
            "email"
        ],
        "dateCreated": dtNow,
    }
    try:
        table.put_item(Item=item)
    except Exception as e:
        print(e)
        response["statusCode"] = 400
        response["message"] = e
        return response

    print(item)

    return response


def lambda_handler(event: dict, context: dict) -> dict:
    """
    Lambda handler for API calls that try to add a comment
    :param event: Lamdba event dictionary
    :param context: Lambda context disctionary
    :returns: Http response object (statusCode, headers, body)
    """
    print(event)
    response = {
        "statusCode": 200,
        "body": "",
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Credentials": True,
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Methods": "OPTIONS,POST,GET",
        },
    }

    try:
        if isinstance(event["body"], str):
            event["body"] = json.loads(event["body"])
    except Exception as e:
        response["statusCode"] = 400
        response["body"] = {"message": e}
        return response

    pathParameters = event.get("pathParameters", {})
    print(pathParameters)

    try:
        # error if no assetId in api call
        if "assetId" not in pathParameters:
            message = "No assetId in API Call"
            response["statusCode"] = 400
            response["body"] = json.dumps({"message": message})
            return response

        split_arr = pathParameters["assetVersionId:commentId"].split(":")
        print("Validating parameters")
        (valid, message) = validate(
            {
                "assetId": {"value": pathParameters["assetId"], "validator": "ID"},
                "commentId": {"value": split_arr[1], "validator": "ID"},
            }
        )

        if not valid:
            print(message)
            response["body"] = json.dumps({"message": message})
            response["statusCode"] = 400
            return response

        print("Trying to add comment")
        # call the add_comment function if everything is valid
        returned = add_comment(
            pathParameters["assetId"], pathParameters["assetVersionId:commentId"], event
        )
        response["statusCode"] = returned["statusCode"]
        response["body"] = json.dumps({"message": returned["message"]})
        print(response)
        return response
    except Exception as e:
        print(f"caught exception: {e}")
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            response["statusCode"] = 500
            response["body"] = json.dumps(
                {
                    "message": "comment "
                    + str(
                        event["body"]["assetVersionId:commentId"] + " already exists."
                    )
                }
            )
            return response
        else:
            response["statusCode"] = 500
            print("Error!", e.__class__, "occurred.")
            try:
                print(e)
                response["body"] = json.dumps({"message": str(e)})
            except:
                print("Can't Read Error")
                response["body"] = json.dumps(
                    {
                        "message": "An unexpected error occurred while executing the request"
                    }
                )
            return response
